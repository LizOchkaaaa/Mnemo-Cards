// Файл страницы прохождения обучения

"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  getCachedMnemo,
  getDictionaryWords,
  getPronunciation,
  guessPronunciationLang,
  pronunciationLangToWebSpeech,
  resolveImageUrl,
  submitSrsReview,
  useMnemoGenerationPending,
  type MnemoResponse,
  type UserWord,
} from "@/lib/api";
import {
  filterWordsDueForLesson,
  sortWordsBySrsSessionPriority,
} from "@/lib/srsSessionPriority";

// Нормализуем
function normalizedWordLangCode(w: Pick<UserWord, "word_language">): string {
  const raw = (w.word_language ?? "en").trim().toLowerCase();
  return (raw.slice(0, 2) || "en") as string;
}

// Оценка SM-2
const SRS_QUALITY_STEPS_KNOW: { q: number; label: string }[] = [
  { q: 1, label: "1" },
  { q: 2, label: "2" },
  { q: 3, label: "3" },
  { q: 4, label: "4" },
  { q: 5, label: "5" },
];

// Иконка динамика
function IconSpeaker() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}

// Перемешиваем массив (алгоритм Фишера-Йетса)
function shuffle<T>(arr: T[]): T[] {
  // Создаём копию
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    // Случайный индекс от 0 до i
    const j = Math.floor(Math.random() * (i + 1));
    // Меняем местами элементы
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

// Запасной TTS браузера
function speakWordTTS(word: string, langIso?: string) {
  if (typeof window === "undefined" || !word.trim()) return;
  // Получаем API синтеза речи браузера
  const u = window.speechSynthesis;
  if (!u) return;
  // Определяем язык
  const code = langIso ?? guessPronunciationLang(word);
  // Отменяем текущее произношение
  u.cancel();
  // Создаём речевой объект
  const utterance = new SpeechSynthesisUtterance(word.trim());
  // Устанавливаем язык в формате BCP 47
  utterance.lang = pronunciationLangToWebSpeech(code);
  // Пытаемся найти подходящий голос
  const lc = utterance.lang.split("-")[0] ?? code;
  const vo = u.getVoices().find((v) => v.lang.startsWith(lc));
  if (vo) utterance.voice = vo;
  // Запускаем произношение
  u.speak(utterance);
}

// Сначала сервер, затем браузерный TTS
function playWordPronunciation(word: string, langIso?: string) {
  if (typeof window === "undefined" || !word.trim()) return;
  // Определяем язык
  const pl = langIso ?? guessPronunciationLang(word);
  // Запрашиваем аудио с сервера
  getPronunciation(word, { lang: pl })
    .then((audioUrl) => {
      if (audioUrl) {
        const audio = new Audio(audioUrl);
        audio.play().catch(() => speakWordTTS(word, pl));
      } else {
        speakWordTTS(word, pl);
      }
    })
    .catch(() => speakWordTTS(word, pl));
}

// Страница прохождения обучения
export default function LearningRunPage() {
  const router = useRouter();                                                                                // Навигация
  const mnemoGenerating = useMnemoGenerationPending();                                                       // Идёт ли генерация мнемоники
  const searchParams = useSearchParams();                                                                    // Параметры URL
  const questionsParam = Math.min(50, Math.max(1, parseInt(searchParams.get("questions") ?? "5", 10) || 5)); // Количество вопросов
  const studyTime = Math.min(120, Math.max(5, parseInt(searchParams.get("time") ?? "20", 10) || 20));        // Время на изучение
  const reviewTime = 10;                                                                                     // Время на повторение слова
  const favoritesOnly = searchParams.get("favorites") === "1";                                               // Только избранные слова
  const orderMode = searchParams.get("order") === "random" ? "random" : "srs";                               // Порядок карточек
  const categoriesStr = searchParams.get("categories") ?? "";                                                // Категории
  const langParamRaw = searchParams.get("lang");                                                             // Язык

  const categoriesParam = useMemo(
    () => (categoriesStr ? categoriesStr.split(",").filter(Boolean) : []),
    [categoriesStr]
  );

  const langFilter = useMemo(() => {
    const s = langParamRaw?.trim().toLowerCase().slice(0, 2) ?? "";
    return /^[a-z]{2}$/.test(s) ? s : null;
  }, [langParamRaw]);

  const [allWords, setAllWords] = useState<UserWord[]>([]); // Все слова пользователя
  const [loading, setLoading] = useState(true);             // Загрузка данных
  const [error, setError] = useState<string | null>(null);  // Ошибка загрузки

  const [sessionWords, setSessionWords] = useState<UserWord[]>([]);                   // Слова в текущей сессии
  const [currentIndex, setCurrentIndex] = useState(0);                                // Индекс текущей карточки
  const [isFlipped, setIsFlipped] = useState(false);                                  // Перевернута ли карточка
  const [timeLeft, setTimeLeft] = useState(studyTime);                                // Осталось времени
  const [knownCount, setKnownCount] = useState(0);                                    // Счётчик изученных слов
  const [unknownCount, setUnknownCount] = useState(0);                                // Счётчик невыученных слов
  const [sessionComplete, setSessionComplete] = useState(false);                      // Сессия завершена
  const [flipOutcome, setFlipOutcome] = useState<"dont_know" | "know" | null>(null);  // Куда нажали

  const [mnemoVerse, setMnemoVerse] = useState<string | null>(null);        // Стихотворение
  const [mnemoImageUrl, setMnemoImageUrl] = useState<string | null>(null);  // URL изображения

  const timerRef = useRef<NodeJS.Timeout | null>(null);   // Ссылка на интервал таймера
  const lastCountedUnknownIndexRef = useRef<number>(-1);  // Для избежания двойного учёта "не знаю"
  const verseForWordRef = useRef<string | null>(null);    // Для какого слова загружали мнемонику

  // Нельзя проходить обучение, пока идет генерация
  useEffect(() => {
    if (mnemoGenerating) {
      router.replace("/learning");
    }
  }, [mnemoGenerating, router]);

  // Загружаем слова пользователя
  useEffect(() => {
    setLoading(true);
    getDictionaryWords()
      .then(setAllWords)
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Ошибка загрузки слов");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Формируем сессию обучения при изменении фильтров или загрузке слов
  useEffect(() => {
    if (allWords.length === 0) return;

    let filtered = [...allWords];

    // Tолько избранные
    if (favoritesOnly) {
      filtered = filtered.filter(w => w.is_favorite);
    }

    // По категориям
    if (categoriesParam.length > 0) {
      filtered = filtered.filter(w => w.category && categoriesParam.includes(w.category));
    }

    // По языку
    if (langFilter) {
      filtered = filtered.filter((w) => normalizedWordLangCode(w) === langFilter);
    }

    // Только то, что по SRS уже «должно» показываться
    filtered = filterWordsDueForLesson(filtered);

    // Сортируем и выбираем нужное количество
    const ordered =
      orderMode === "random"
        ? shuffle(filtered) // Случайный порядок
        : sortWordsBySrsSessionPriority(filtered); // По срочности повторения

    const selected = ordered.slice(0, questionsParam);

    // Сбрасываем состояния сессии
    setSessionWords(selected);
    setCurrentIndex(0);
    setIsFlipped(false);
    setTimeLeft(studyTime);
    setKnownCount(0);
    setUnknownCount(0);
    setSessionComplete(false);
    lastCountedUnknownIndexRef.current = -1;
    setFlipOutcome(null);
  }, [allWords, favoritesOnly, categoriesParam, langFilter, questionsParam, studyTime, orderMode]);

  // Загружаем карточку
  useEffect(() => {
    if (sessionWords.length === 0 || currentIndex >= sessionWords.length) {
      verseForWordRef.current = null;
      setMnemoVerse(null);
      setMnemoImageUrl(null);
      return;
    }

    // Получаем слово
    const word = sessionWords[currentIndex].word;
    verseForWordRef.current = word;
    setMnemoVerse(null);
    setMnemoImageUrl(null);

    let cancelled = false;  // Флаг отмены при смене слова
    let intervalId: ReturnType<typeof setInterval> | null = null;

    // Добавляем стихотворение и изображение
    const apply = (res: MnemoResponse) => {
      const phrase = (res.mnemonic_phrase_ru || "").trim();
      const img = resolveImageUrl(res.image_url ?? null);
      setMnemoVerse(phrase || null);
      setMnemoImageUrl(img);
      const has = Boolean(phrase || img);
      if (has && intervalId) {
        clearInterval(intervalId);
        intervalId = null;
      }
    };

    const tryLoad = () => {
      if (cancelled || verseForWordRef.current !== word) return;
      // Пытаемся получить закэшированную мнемокарточку
      getCachedMnemo(word)
        .then((res) => {
          if (cancelled || verseForWordRef.current !== word) return;
          apply(res);
        })
        .catch(() => {
          if (cancelled || verseForWordRef.current !== word) return;
        });
    };

    tryLoad();  // Первая попытка
    
    // Каждые 3 секунды проверяем, не сгенерировалась ли мнемоника
    let polls = 0;
    const maxPolls = 60;
    intervalId = setInterval(() => {
      if (cancelled || verseForWordRef.current !== word) {
        if (intervalId) clearInterval(intervalId);
        return;
      }
      polls += 1;
      if (polls > maxPolls) {
        if (intervalId) clearInterval(intervalId);
        return;
      }
      tryLoad();
    }, 3000);

    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [sessionWords, currentIndex]);

  // Отправляем оценку
  const advanceAfterSrs = useCallback(
    (quality: number) => {
      // Останавливаем таймер
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      
      const w = sessionWords[currentIndex];
      if (!w) return;
      
      // Отправляем результат на сервер для обновления SRS интервала
      submitSrsReview(w.id, quality).catch(() => {});
      
      // Обновляем счётчики: quality >= 3, то правильный ответ
      if (quality >= 3) setKnownCount((p) => p + 1);
      else setUnknownCount((p) => p + 1);
      
      const nextIndex = currentIndex + 1;
      if (nextIndex >= sessionWords.length) {
        // Сессия завершена
        setSessionComplete(true);
        setFlipOutcome(null);
      } else {
        // Переходим к следующей карточке
        setCurrentIndex(nextIndex);
        setIsFlipped(false);
        setFlipOutcome(null);
        setTimeLeft(studyTime);
      }
    },
    [currentIndex, sessionWords, studyTime]
  );

  // Таймер
  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (sessionComplete || sessionWords.length === 0 || currentIndex >= sessionWords.length) {
      return;
    }

    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        const newTime = prev - 1;

        if (newTime <= 0) {
          // Время истекло
          if (!isFlipped) {
            // Время на лицевой стороне
            setFlipOutcome("dont_know");
            setIsFlipped(true);
            return reviewTime;
          } else {
            // Время на обратной стороне без нажатия считаем как ошибку
            if (lastCountedUnknownIndexRef.current !== currentIndex) {
              lastCountedUnknownIndexRef.current = currentIndex;
              advanceAfterSrs(flipOutcome === "know" ? 1 : 0);
            }
            return studyTime;
          }
        }
        
        return newTime;
      });
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [currentIndex, isFlipped, sessionComplete, sessionWords.length, studyTime, reviewTime, advanceAfterSrs, flipOutcome]);
  
  // Нажатие "Не знаю"
  const flipDontKnow = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setFlipOutcome("dont_know");
    setIsFlipped(true);
    setTimeLeft(reviewTime);
  };

  // Нажатие "Знаю"
  const flipKnow = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setFlipOutcome("know");
    setIsFlipped(true);
    setTimeLeft(reviewTime);
  };

  const currentWord = sessionWords[currentIndex];
  const phaseText = isFlipped ? "Просмотр перевода" : "Изучение слова";

  // Состояние загрузки
  if (loading) {
    return (
      <section className="glass glass-result">
        <div className="loading-dots" aria-hidden>
          <span /><span /><span />
        </div>
        <p className="app-muted" style={{ marginTop: 16 }}>Загрузка слов...</p>
      </section>
    );
  }

  // Состояние ошибки
  if (error) {
    return (
      <section className="glass glass-result">
        <p className="app-error">{error}</p>
        <Link href="/learning" className="app-btn-outline" style={{ display: "inline-block", marginTop: 16 }}>
          ← Назад к настройкам
        </Link>
      </section>
    );
  }

  if (sessionWords.length === 0) {
    return (
      <section className="glass glass-result">
        <h2 className="app-title">Обучение</h2>
        <p className="app-muted" style={{ marginTop: 8 }}>
          Нет слов для тренировки. Добавьте слова в словарь или измените настройки
        </p>
        <Link href="/learning" className="app-btn-outline" style={{ display: "inline-block", marginTop: 16 }}>
          ← Назад к настройкам
        </Link>
      </section>
    );
  }

  // Экран статистики обучения
  if (sessionComplete) {
    return (
      <section className="glass glass-result learning-run">
        <h2 className="app-title">Обучение завершено</h2>
        <p className="app-muted" style={{ marginTop: 12 }}>
          <strong style={{ color: "#4CAF50" }}>Знаете: {knownCount}</strong><br />
          <strong style={{ color: "#f44336" }}>Не знаете: {unknownCount}</strong><br />
        </p>
        <Link href="/learning" className="app-btn-gradient" style={{ display: "inline-block", marginTop: 24 }}>
          На страницу обучение
        </Link>
      </section>
    );
  }

  return (
    <section className="glass glass-result glass-result--wide learning-run">
      <div className="learning-run-header">
        <Link href="/learning" className="learning-run-back">
          ← Настройки
        </Link>
        <span className="learning-run-progress">
          Карточка {currentIndex + 1} из {sessionWords.length} • {phaseText}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Link
            href="/learning"
            className="learning-run-close"
            aria-label="Выйти из обучения"
            title="Выйти"
          >
            ×
          </Link>
        </div>
      </div>

      <div className="learning-run-timer" aria-live="polite">
        <span className="learning-run-timer-value">{timeLeft}</span>
        <span className="learning-run-timer-unit">сек</span>
      </div>

      <div className={`learning-run-card ${isFlipped ? "flipped" : ""}`}>
        <div className="learning-run-card-inner">
          <div className="learning-run-card-face learning-run-card-front">
            <div className="learning-run-card-word-row">
              <p className="learning-run-card-word">{currentWord.word}</p>
              <button
                type="button"
                className="learning-run-speaker"
                onClick={(e) => {
                  e.stopPropagation();
                  playWordPronunciation(currentWord.word, currentWord.word_language);
                }}
                aria-label="Прослушать слово"
              >
                <IconSpeaker />
              </button>
            </div>
            {currentWord.transcription && (
              <p className="learning-run-card-transcription">[{currentWord.transcription}]</p>
            )}
            {mnemoVerse && (
              <p className="learning-run-card-hint">Попытайся вспомнить слово</p>
            )}
          </div>

          <div className="learning-run-card-face learning-run-card-back">
            <div className="learning-run-card-back-text">
              <div className="learning-run-card-back-header">
                <p className="learning-run-card-translation">{currentWord.translation}</p>
                <div className="learning-run-card-back-word-row">
                  <p className="learning-run-card-word learning-run-card-word--small">{currentWord.word}</p>
                  <button
                    type="button"
                    className="learning-run-speaker learning-run-speaker--small"
                    onClick={(e) => {
                      e.stopPropagation();
                      playWordPronunciation(currentWord.word, currentWord.word_language);
                    }}
                    aria-label="Прослушать слово"
                    title="Прослушать слово"
                  >
                    <IconSpeaker />
                  </button>
                </div>
                {currentWord.transcription && (
                  <p className="learning-run-card-transcription learning-run-card-transcription--back">
                    [{currentWord.transcription}]
                  </p>
                )}
              </div>
     
              {mnemoVerse && (
                <div className="learning-run-card-verse" aria-label="Мнемоническое стихотворение">
                  {mnemoVerse.split("\n").map((line, i) => (
                    <p key={i} className="learning-run-card-verse-line">
                      {line}
                    </p>
                  ))}
                </div>
              )}

              {isFlipped && mnemoVerse && !mnemoImageUrl && (
                <p className="learning-run-card-no-image app-muted" role="status">
                  Нет изображения. Попробуйте ещё раз добавить слово в словарь
                </p>
              )}
            </div>

            {mnemoImageUrl && (
              <div className="learning-run-card-image-wrap" aria-hidden={!mnemoVerse}>
                <img
                  src={mnemoImageUrl}
                  alt=""
                  className="learning-run-card-image"
                  loading="lazy"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="learning-run-actions">
        {!isFlipped ? (
          <>
            <button
              type="button"
              className="learning-run-btn learning-run-btn--no"
              onClick={flipDontKnow}
            >
              Не знаю
            </button>
            <button
              type="button"
              className="learning-run-btn learning-run-btn--yes"
              onClick={flipKnow}
            >
              Знаю
            </button>
          </>
        ) : flipOutcome === "know" ? (

          <div className="learning-run-srs">
            <p className="learning-run-srs-hint app-muted">Оцените степень запоминания слова</p>
            <div className="learning-run-srs-row learning-run-srs-row--know" role="group" aria-label="Оценка от 1 до 5">
              {SRS_QUALITY_STEPS_KNOW.map(({ q, label }) => (
                <button
                  key={q}
                  type="button"
                  className={`learning-run-srs-btn ${q < 3 ? "learning-run-srs-btn--low" : "learning-run-srs-btn--high"}`}
                  onClick={() => advanceAfterSrs(q)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        ) : (

          <button
            type="button"
            className="learning-run-btn learning-run-btn--next"
            onClick={() => advanceAfterSrs(0)}
          >
            Дальше
          </button>
        )}
      </div>
    </section>
  );
}