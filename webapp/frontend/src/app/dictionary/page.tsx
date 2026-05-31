// Файл страницы словаря

"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import Link from "next/link";
import {
  addDictionaryWord,
  deleteDictionaryWord,
  exportCardsToDocx,
  generateMnemo,
  getAutoTranslationLangPair,
  getDecomposition,
  getDictionaryCategories,
  getDictionaryWords,
  getPronunciation,
  guessPronunciationLang,
  getStoredVerseLearningLang,
  getTranscription,
  getTranslation,
  pronunciationLangToWebSpeech,
  updateDictionaryWord,
  useMnemoGenerationPending,
  type UserWord,
} from "@/lib/api";
import { parseDictionaryImportText } from "@/lib/dictionaryImport";

// Фильтр языка
const WORD_LANGUAGE_LABELS: Record<string, string> = {
  en: "Английский",
  de: "Немецкий",
  fr: "Французский",
  es: "Испанский",
  it: "Итальянский",
};

// Нормализуем
function normalizedWordLangCode(w: Pick<UserWord, "word_language">): string {
  const raw = (w.word_language ?? "en").trim().toLowerCase();
  return (raw.slice(0, 2) || "en") as string;
}

// Обратное преобразование
function wordLanguageFilterLabel(code: string): string {
  const c = code.trim().toLowerCase().slice(0, 2);
  return WORD_LANGUAGE_LABELS[c] ?? code.toUpperCase();
}

// Категории по умолчанию
const DEFAULT_CATEGORIES = [
  "Животные",
  "Еда и напитки", 
  "Семья", 
  "Природа",
  "Другое"
];

// Озвучиваем слово через Web Speech API
function speakTTS(word: string, langIso?: string) {
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

// Отображаем слово в словаре
function WordCard({
  entry,                    // Данные слова
  decomposition,            // Декомпозиция
  menuOpen,                 // Открыто ли меню
  onToggleMenu,             // Функция, которая переключает меню (открыть/закрыть)
  onEdit,                   // Функция для редактирования слова
  onDelete,                 // Функция для удаления слова
  onToggleFavorite,         // Функция для добавления/удаления из избранного
  learningLinkBlocked,      // Заблокирована ли ссылка на обучение
  decompositionLoading,     // Идёт ли загрузка декомпозиции с сервера
}: {
  entry: UserWord;
  decomposition: { parts: string[] } | null;
  decompositionLoading?: boolean;
  menuOpen: boolean;
  onToggleMenu: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onToggleFavorite: () => void;
  learningLinkBlocked?: boolean;
}) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Закрываем меню при клике в любое место вне
  useEffect(() => {
    if (!menuOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        // Закрываем меню
        onToggleMenu();
      }
    }
  
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen, onToggleMenu]);

  // Проверка на наличие декомпозиции
  const hasDecomposition = decomposition?.parts && decomposition.parts.length >= 1;

  return (
    <li className="dict-word-card">
      <button
        type="button"
        className="dict-star"
        onClick={onToggleFavorite}
        aria-label={entry.is_favorite ? "Убрать из избранного" : "В избранное"}
        title={entry.is_favorite ? "Убрать из избранного" : "В избранное"}
      >
        {entry.is_favorite ? (
          <span className="dict-star-filled" aria-hidden>★</span>
        ) : (
          <span className="dict-star-empty" aria-hidden>☆</span>
        )}
      </button>

      <div className="dict-word-body">
        <div className="dict-word-row">
          {learningLinkBlocked ? (
            <span
              className="dict-word-link dict-word-link--disabled"
              title="Дождитесь окончания генерации карточки"
            >
              {entry.word}
            </span>
          ) : (
            <Link href={`/learning?word=${encodeURIComponent(entry.word)}`} className="dict-word-link">
              {entry.word}
            </Link>
          )}

          {decompositionLoading && !hasDecomposition && (
            <span className="dict-decomposition dict-decomposition--loading app-muted" title="Запрос разбора слова" aria-live="polite">
              Подождите, идёт декомпозиция слова...
            </span>
          )}
          {hasDecomposition && (
            <span className="dict-decomposition" title="Декомпозиция слова">
              {decomposition!.parts.join(" + ")}
            </span>
          )}

          {entry.category && (
            <span className="dict-category-badge">{entry.category}</span>
          )}
        </div>

        {entry.transcription && (
          <p className="dict-transcription">[{entry.transcription}]</p>
        )}

        <p className="dict-translation">{entry.translation}</p>
      </div>

      <button
        type="button"
        className="dict-speaker"
        aria-label="Прослушать произношение"
        title="Прослушать произношение"
        onClick={() => {
          if (!entry.word?.trim()) return;
          const lang = (entry.word_language && entry.word_language.trim()) || guessPronunciationLang(entry.word);
          getPronunciation(entry.word, { lang })
            .then((url) => {
              if (url) {
                const a = new Audio(url);
                a.play().catch(() => speakTTS(entry.word, lang));
              } else {
                speakTTS(entry.word, lang);
              }
            })
            .catch(() => speakTTS(entry.word, lang));
        }}
      >
        <span aria-hidden>🔊</span>
      </button>

      <div className="dict-menu-wrap" ref={menuRef}>
        <button
          type="button"
          className="dict-menu-btn"
          onClick={onToggleMenu}
          aria-label="Меню"
          aria-expanded={menuOpen}
        >
          <span aria-hidden>⋮</span>
        </button>
        
        {menuOpen && (
          <div className="dict-menu-dropdown" role="menu">
            <button type="button" role="menuitem" onClick={onEdit}>
              Редактировать
            </button>
            <button type="button" role="menuitem" onClick={onDelete}>
              Удалить
            </button>
          </div>
        )}
      </div>
    </li>
  );
}

// Форма для добавления или редактирования слова
function WordFormModal({
  title,                     // "Добавить слово" или "Редактировать слово"
  initialWord,               // Слово
  initialTranslation,        // Перевод
  initialTranscription,      // Транскрипция
  initialCategory,           // категория
  initialFavorite,           // В избранном?
  initialWordLanguage,       // Изучаемый язык
  categories,                // Список всех категорий
  onSave,                    // Функция, которая сохраняет слово
  onClose,                   // Функция, которая закрывает форму
  onClearError,              // Функция, которая очищает сообщение об ошибке
  error,                     // Текст ошибки
  saving                     // Идёт сохранение?
}: {
  title: string;
  initialWord: string;
  initialTranslation: string;
  initialTranscription: string;
  initialCategory: string;
  initialFavorite: boolean;
  initialWordLanguage: string;
  categories: string[];
  onSave: (
    word: string,
    translation: string,
    category: string,
    transcription: string,
    is_favorite: boolean,
    word_language: string
  ) => void;
  onClose: () => void;
  onClearError?: () => void;
  error?: string | null;
  saving?: boolean;
}) {
  const categoryWrapRef = useRef<HTMLDivElement>(null);
  // Каждое поле формы хранит своё значение в отдельной переменной
  const [word, setWord] = useState(initialWord);                            // Слово
  const [translation, setTranslation] = useState(initialTranslation);       // Перевод
  const [transcription, setTranscription] = useState(initialTranscription); // Транскрипция
  const [category, setCategory] = useState(initialCategory);                // Категория
  const [categoryOpen, setCategoryOpen] = useState(false);                  // Показан выпадающий список категорий?
  const [isFavorite, setFavorite] = useState(initialFavorite);              // В избранном?

  // Состояния загрузки
  const [transcriptionLoading, setTranscriptionLoading] = useState(false); // Загружается транскрипция?
  const [translationLoading, setTranslationLoading] = useState(false);     // Загружается перевод?

  // Таймеры
  const transcriptionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null); // Таймер для транскрипции
  const translationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);   // Таймер для перевода
  
  // Флаг: пользователь сам вручную правил транскрипцию
  const transcriptionEditedByUserRef = useRef(false);
  // Запоминаем, для какого слова мы в последний раз подставляли транскрипцию
  const lastAutoTranscriptionWordRef = useRef("");

  // Закрываем выпадающий список категорий при клике вне
  useEffect(() => {
    if (!categoryOpen) return;
    
    function handleClickOutside(e: MouseEvent) {
      // Если кликнули вне блока с категориями
      if (categoryWrapRef.current && !categoryWrapRef.current.contains(e.target as Node)) {
        setCategoryOpen(false); // Закрываем список
      }
    }
    
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [categoryOpen]);

  // Фильтрация категорий по введённому тексту
  const categoryFiltered = category.trim()
    ? categories.filter((c) => c.toLowerCase().includes(category.trim().toLowerCase()))
    : categories;

  // Автоматическая подстановка транскрипции
  useEffect(() => {
    const w = word.trim();
    
    // Если слова нет, то очищаем транскрипцию
    if (!w) {
      setTranscription("");
      transcriptionEditedByUserRef.current = false;
      lastAutoTranscriptionWordRef.current = "";
      return;
    }

    // Если пользователь ввёл НОВОЕ слово, то сбрасываем флаг "ручное редактирование"
    if (w !== lastAutoTranscriptionWordRef.current) {
      transcriptionEditedByUserRef.current = false;
    }

    // Если пользователь сам ввел
    if (transcriptionEditedByUserRef.current && w === lastAutoTranscriptionWordRef.current) {
      return;
    }

    // Отменяем предыдущий таймер
    if (transcriptionTimeoutRef.current) {
      clearTimeout(transcriptionTimeoutRef.current);
    }

    // Запоминаем слово, для которого запускаем таймер
    const capturedWord = w;
    
    // Запускаем новый таймер на 400 мс
    transcriptionTimeoutRef.current = setTimeout(() => {
      // Показываем "Загрузка..."
      setTranscriptionLoading(true);

      // Запрос транскрипции к серверу
      getTranscription(capturedWord, initialWordLanguage)
        .then((t) => {
          setTranscription(t);
          lastAutoTranscriptionWordRef.current = capturedWord; // Запоминаем слово
          transcriptionEditedByUserRef.current = false;        // Сбрасываем флаг
        })
        .catch(() => setTranscription(""))
        .finally(() => {
          setTranscriptionLoading(false);
          transcriptionTimeoutRef.current = null; // Очищаем таймер
        });
    }, 400);

    // При смене слова отменяем таймер
    return () => {
      if (transcriptionTimeoutRef.current) clearTimeout(transcriptionTimeoutRef.current);
    };
  }, [word, initialWordLanguage]);

  // Автоматический перевод слова
  useEffect(() => {
    const w = word.trim();
    if (!w) return;

    // Отменяем предыдущий таймер
    if (translationTimeoutRef.current) {
      clearTimeout(translationTimeoutRef.current);
    }

    // Запускаем новый таймер на 500 мс
    translationTimeoutRef.current = setTimeout(() => {
      setTranslationLoading(true);
      // Запрос перевода к серверу
      getTranslation(w, getAutoTranslationLangPair(initialWordLanguage))
        .then((t) => {
          // Устанавливаем перевод
          if (t) setTranslation(t);
        })
        .catch(() => {})
        .finally(() => {
          setTranslationLoading(false);
          translationTimeoutRef.current = null;
        });
    }, 500);

    return () => {
      if (translationTimeoutRef.current) clearTimeout(translationTimeoutRef.current);
    };
  }, [word, initialWordLanguage]);

  // Сброс всех полей при открытии формы
  useEffect(() => {
    setWord(initialWord);
    setTranslation(initialTranslation);
    setTranscription(initialTranscription);
    setCategory(initialCategory);
    setFavorite(initialFavorite);
    transcriptionEditedByUserRef.current = false;
    lastAutoTranscriptionWordRef.current = (initialWord || "").trim();
  }, [
    initialWord,
    initialTranslation,
    initialTranscription,
    initialCategory,
    initialFavorite,
    initialWordLanguage,
  ]);

  return (
    <div className="dict-modal-backdrop" onClick={onClose} role="presentation">
      <div className="dict-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="dict-modal-title">
        <h3 id="dict-modal-title" className="app-title">{title}</h3>

        {error && <p className="app-error" style={{ marginTop: 12 }}>{error}</p>}

        {saving && <p className="app-muted" style={{ marginTop: 8 }}>Сохранение...</p>}

        <form
          className="dict-form"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(
              word.trim(),
              translation.trim(),
              category.trim(),
              transcription.trim(),
              isFavorite,
              initialWordLanguage
            );
          }}
        >
          
          <label>
            Слово
            <input
              type="text"
              value={word}
              onChange={(e) => {
                setWord(e.target.value);
                onClearError?.();
              }}
              placeholder="Например, apple"
              required
              disabled={saving}
            />
          </label>

          <label>
            Транскрипция
            <input
              type="text"
              value={transcription}
              onChange={(e) => {
                setTranscription(e.target.value);
                transcriptionEditedByUserRef.current = true;
                onClearError?.();
              }}
              placeholder={transcriptionLoading ? "Загрузка..." : "Автоматически или введите вручную"}
              disabled={saving}
            />
          </label>

          <label>
            Перевод
            <input
              type="text"
              value={translation}
              onChange={(e) => {
                setTranslation(e.target.value);
                onClearError?.();
              }}
              placeholder={translationLoading ? "Загрузка..." : "Автоматически или введите вручную"}
              required
              disabled={saving}
            />
          </label>

          <label>
            Категория
            <div className="dict-category-wrap" ref={categoryWrapRef}>
              <input
                type="text"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  onClearError?.();
                }}
                onFocus={() => setCategoryOpen(true)}
                onClick={() => setCategoryOpen(true)}
                placeholder="Выберите из списка или задайте свою"
                disabled={saving}
                autoComplete="off"
              />
              
              {categoryOpen && !saving && (
                <div className="dict-category-dropdown" role="listbox">
                  {categoryFiltered.length === 0 ? (
                    <div className="dict-category-empty">
                      {categories.length === 0
                        ? "Пока нет категорий. Введите свою и сохраните слово"
                        : "Нет подходящих. Введите новую категорию выше"}
                    </div>
                  ) : (
                    categoryFiltered.map((c) => (
                      <button
                        key={c}
                        type="button"
                        role="option"
                        className="dict-category-option"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setCategory(c);
                          setCategoryOpen(false);
                        }}
                      >
                        {c}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </label>

          <label className="dict-check">
            <input
              type="checkbox"
              checked={isFavorite}
              onChange={(e) => setFavorite(e.target.checked)}
              disabled={saving}
            />
            <span>В избранном</span>
          </label>

          <div className="dict-form-actions">
            <button type="button" className="secondary" onClick={onClose} disabled={saving}>
              Отмена
            </button>
            <button type="submit" disabled={saving}>Сохранить</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Страница "Мой словарь"
export default function DictionaryPage() {
  const mnemoGenerating = useMnemoGenerationPending();             // Идёт генерация мнемоники?
  const [userWords, setUserWords] = useState<UserWord[]>([]);      // Все слова пользователя
  const [categories, setCategories] = useState<string[]>([]);      // Категории
  const [loading, setLoading] = useState(true);                    // Загружаются слова?
  const [dictError, setDictError] = useState<string | null>(null); // Ошибка загрузки

  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);       // Какое меню открыто (по id слова)
  const [modal, setModal] = useState<"add" | "edit" | null>(null);         // Какая форма открыта?
  const [editingEntry, setEditingEntry] = useState<UserWord | null>(null); // Какое слово редактируем
  const [saving, setSaving] = useState(false);                             // Идёт сохранение?
  const [formError, setFormError] = useState<string | null>(null);         // Ошибка формы

  const [decompositionMap, setDecompositionMap] = useState<Record<string, { parts: string[] }>>({});         // Части
  const [decompositionLoadingByWord, setDecompositionLoadingByWord] = useState<Record<string, boolean>>({}); // Для каких слов идёт загрузка?

  const [exporting, setExporting] = useState(false);

  const [categoryFilter, setCategoryFilter] = useState<string | null>(null); // Выбранная категория для фильтра
  const [categoryFilterOpen, setCategoryFilterOpen] = useState(false);       // Открыт ли фильтр?
  const categoryFilterRef = useRef<HTMLDivElement>(null);                    // Ссылка на фильтр (для закрытия при клике вне)

  const [languageFilter, setLanguageFilter] = useState<string | null>(null); // Код языка word_language или null = все
  const [languageFilterOpen, setLanguageFilterOpen] = useState(false);       // Открыт ли фильтр?
  const languageFilterRef = useRef<HTMLDivElement>(null);                    // Ссылка на фильтр (для закрытия при клике вне)

  const dictionaryImportInputRef = useRef<HTMLInputElement>(null);           // Скрытый input type="file"
  const [importing, setImporting] = useState(false);                         // Идёт импорт?
  const [importProgress, setImportProgress] = useState<string | null>(null); // Прогресс импорта

  // Закрытие фильтра категорий при клике вне
  useEffect(() => {
    if (!categoryFilterOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (categoryFilterRef.current && !categoryFilterRef.current.contains(e.target as Node)) {
        setCategoryFilterOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [categoryFilterOpen]);

  // Закрытие фильтра языка при клике вне
  useEffect(() => {
    if (!languageFilterOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (languageFilterRef.current && !languageFilterRef.current.contains(e.target as Node)) {
        setLanguageFilterOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [languageFilterOpen]);

  // Загрузка категорий при открытии формы добавления/редактирования
  useEffect(() => {
    if (modal === "add" || modal === "edit" || userWords.length > 0) {
      getDictionaryCategories().then(setCategories).catch(() => setCategories([]));
    }
  }, [modal, userWords.length]);

  // Вычисляем уникальные категории из слов пользователя
  const categoriesFromWords = useMemo(
    () => Array.from(new Set(userWords.map((w) => w.category).filter((c): c is string => !!c?.trim()))).sort(),
    [userWords]
  );

  // Языки из сохранённых карточек
  const languagesFromWords = useMemo(() => {
    const codes = userWords.map((w) => normalizedWordLangCode(w));
    return Array.from(new Set(codes)).sort();
  }, [userWords]);

  // Языки
  const languageFilterOptions = useMemo(() => {
    if (languagesFromWords.length > 0) return languagesFromWords;
    return Object.keys(WORD_LANGUAGE_LABELS).sort();
  }, [languagesFromWords]);

  // Категории
  const categoryFilterOptions = useMemo(() => {
    if (categoriesFromWords.length > 0) return categoriesFromWords;
    return [...DEFAULT_CATEGORIES];
  }, [categoriesFromWords]);

  // Загрузка декомпозиции
  useEffect(() => {
    if (userWords.length === 0) return;
    // Уникальный ключ (слово + перевод)
    const key = (w: string, t: string) => `${w}\t${t}`;
    const seen = new Set<string>();

    userWords.forEach((entry) => {
      // У слова уже есть декомпозиция в базе данных
      if (entry.parts && entry.parts.length > 0) {
        // Сохраняем в состояние
        setDecompositionMap((prev) => ({ ...prev, [entry.word]: { parts: entry.parts! } }));
        // Убираем флаг загрузки для этого слова
        setDecompositionLoadingByWord((prev) => {
          if (!prev[entry.word]) return prev;
          const next = { ...prev };
          delete next[entry.word];
          return next;
        });
        return;
      }

      // Декомпозиции нет, нужно запросить с сервера
      const k = key(entry.word, entry.translation);
      if (seen.has(k)) return;
      seen.add(k);

      const wKey = entry.word;
      
      // Ставим флаг "загружается" для этого слова
      setDecompositionLoadingByWord((prev) => ({ ...prev, [wKey]: true }));

      // Запрашиваем декомпозицию с сервера
      getDecomposition(
          entry.word,
          entry.translation,
          (entry.word_language && entry.word_language.trim()) || getStoredVerseLearningLang(),
        )
        .then((res) => {
          if (res.parts && res.parts.length > 0) {
            // Сохраняем полученные части
            setDecompositionMap((prev) => ({ ...prev, [wKey]: { parts: res.parts } }));
          }
        })
        .catch(() => {})
        .finally(() => {
          // Убираем флаг загрузки
          setDecompositionLoadingByWord((prev) => {
            const next = { ...prev };
            delete next[wKey];
            return next;
          });
        });
    });
  }, [userWords]);

  // Идёт ли хотя бы одна загрузка декомпозиции
  const decompositionInProgress = useMemo(
    () => Object.values(decompositionLoadingByWord).some(Boolean),
    [decompositionLoadingByWord]
  );

  // Все доступные категории
  const allCategories = useMemo(
    () => Array.from(new Set([...DEFAULT_CATEGORIES, ...categories])),
    [categories]
  );

  // Отфильтрованные слова по категории и языку
  const filteredWords = useMemo(() => {
    let list = userWords;
    if (categoryFilter) {
      if (categoryFilter === "__none__") {
        list = list.filter((w) => !(w.category || "").trim());
      } else {
        list = list.filter((w) => (w.category || "").trim() === categoryFilter);
      }
    }
    if (languageFilter) {
      list = list.filter((w) => normalizedWordLangCode(w) === languageFilter);
    }
    return list;
  }, [userWords, categoryFilter, languageFilter]);

  // Есть ли хотя бы одно слово без категории?
  const hasUncategorized = userWords.some((w) => !(w.category || "").trim());

  // Загрузка слов пользователя
  const loadUserWords = useCallback(() => {
    return getDictionaryWords()
      .then((list) => {
        setUserWords(list);
        setDictError(null);
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Ошибка загрузки";
        if (msg.includes("503") || msg.includes("unavailable")) {
          setDictError("Словарь недоступен");
        } else if (msg.includes("401")) {
          setDictError("Войдите в аккаунт, чтобы видеть свой список слов");
        } else {
          setDictError(msg);
        }
        setUserWords([]);
      });
  }, []);

  // Генерация мнемоники после добавления/редактирования слова.
  const runMnemoAfterAdd = useCallback(async (word: string, translation: string) => {
    await generateMnemo({ word, translation });
  }, []);

  // Триггер генерации мнемоники
  const triggerMnemoGeneration = useCallback(
    (word: string, translation: string) => {
      void runMnemoAfterAdd(word, translation).catch((e) => {
        console.warn("[mnemo] генерация не удалась:", e);
      });
    },
    [runMnemoAfterAdd]
  );

  // Импорт слов из файла
  const handleDictionaryImportFile = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const input = e.target;
      const file = input.files?.[0];
      input.value = ""; // Очищаем input
      if (!file) return;

      // Читаем содержимое файла
      let text: string;
      try {
        text = await file.text();
      } catch {
        alert("Не удалось прочитать файл");
        return;
      }

      // Парсим текст
      const pairs = parseDictionaryImportText(text);
      if (pairs.length === 0) {
        alert(
          "Задайте в файле: слово перевод или слово, перевод"
        );
        return;
      }

      // Подтверждение пользователя
      if (
        !confirm(
          `Добавить ${pairs.length} слов(а) из файла? Для каждого запустится генерация карточки. Это может занять некоторое время`
        )
      ) {
        return;
      }

      // Процесс импорта
      setImporting(true);
      let added = 0;
      let skipped = 0;
      const failed: string[] = [];

      for (let i = 0; i < pairs.length; i++) {
        const { word, translation } = pairs[i];
        setImportProgress(`${i + 1} / ${pairs.length}: ${word}`); // Обновляем прогресс
        
        try {
          // Добавляем слово в словарь
          await addDictionaryWord(word, translation, {
            is_favorite: false,
            category: null,
            transcription: null,
          });
          added += 1;
          
          // Запускаем генерацию карточки
          try {
            await runMnemoAfterAdd(word, translation);
          } catch (me) {
            console.warn("[mnemo] после импорта:", word, me);
            failed.push(`${word}: мнемоника — ${me instanceof Error ? me.message : "ошибка"}`);
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          if (msg.includes("409") || msg.includes("уже есть")) {
            skipped += 1; // Слово уже существует в словаре
          } else {
            failed.push(`${word}: ${msg}`);
          }
        }
      }

      setImportProgress(null);
      setImporting(false);
      await loadUserWords(); // Перезагружаем список слов

      // Показываем итоговую статистику
      const summary = [
        `Добавлено: ${added}.`,
        skipped > 0 ? `Пропущено (уже в словаре): ${skipped}.` : "",
        failed.length > 0
          ? `Проблемы:\n${failed.slice(0, 12).join("\n")}${failed.length > 12 ? `\n… и ещё ${failed.length - 12}` : ""}`
          : "",
      ]
        .filter(Boolean)
        .join("\n");
      alert(summary);
    },
    [loadUserWords, runMnemoAfterAdd]
  );

  // Начальная загрузка слов
  useEffect(() => {
    setLoading(true);
    loadUserWords().finally(() => setLoading(false));
  }, [loadUserWords]);

  // Открыть форму добавления слова
  const handleAdd = () => {
    setEditingEntry(null);
    setModal("add");
    setFormError(null);
  };

  // Открыть форму редактирования слова
  const handleEdit = (entry: UserWord) => {
    setMenuOpenId(null);
    setEditingEntry(entry);
    setModal("edit");
    setFormError(null);
  };

  // Сохранение при добавлении нового слова
  const handleSaveAdd = async (
    word: string,
    translation: string,
    category: string,
    transcription: string,
    is_favorite: boolean,
    word_language: string
  ) => {
    setSaving(true);
    setFormError(null);
    try {
      await addDictionaryWord(word, translation, {
        is_favorite,
        category: category || null,
        transcription: transcription || null,
        word_language: word_language || "en",
      });
      setModal(null);
      loadUserWords(); // Перезагружаем список
      triggerMnemoGeneration(word, translation); // Запускаем генерацию мнемоники
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Ошибка сохранения";
      setFormError(msg);
    } finally {
      setSaving(false);
    }
  };

  // Сохранение при редактировании слова
  const handleSaveEdit = async (
    word: string,
    translation: string,
    category: string,
    transcription: string,
    is_favorite: boolean,
    word_language: string
  ) => {
    if (!editingEntry) return;
    setSaving(true);
    setFormError(null);
    try {
      await updateDictionaryWord(editingEntry.id, {
        word,
        translation,
        is_favorite,
        category: category || null,
        transcription: transcription || null,
        word_language: word_language || "en",
      });
      setModal(null);
      setEditingEntry(null);
      loadUserWords();
      triggerMnemoGeneration(word, translation);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Ошибка сохранения";
      setFormError(msg);
    } finally {
      setSaving(false);
    }
  };

  // Удаление слова
  const handleDelete = (entry: UserWord) => {
    setMenuOpenId(null);
    if (!confirm(`Удалить слово «${entry.word}»?`)) return;
    deleteDictionaryWord(entry.id)
      .then(loadUserWords)
      .catch((e) => {
        alert(e instanceof Error ? e.message : "Ошибка удаления");
      });
  };

  // Переключение избранного
  const handleToggleFavorite = (entry: UserWord) => {
    updateDictionaryWord(entry.id, { is_favorite: !entry.is_favorite })
      .then(loadUserWords);
  };

  const handleExportDocxClick = async () => {
    if (filteredWords.length === 0) return;
    setExporting(true);
    try {
      await exportCardsToDocx(filteredWords.map((w) => w.id));
    } catch {
      setFormError("Error DOCX");
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <section className="glass glass-result glass-result--wide">
        <div className="dict-header">
          <h2 className="app-title">Список слов</h2>
          <div className="dict-header-actions">
     
            <div className="dict-filter-label" ref={categoryFilterRef}>
              <div className="dict-filter-wrap">
                <button
                  type="button"
                  className="dict-filter-select"
                  onClick={() => setCategoryFilterOpen((v) => !v)}
                  aria-expanded={categoryFilterOpen}
                  aria-haspopup="listbox"
                  aria-label="Фильтр по категории"
                >
                  {!categoryFilter
                    ? "Все категории"
                    : categoryFilter === "__none__"
                      ? "Без категории"
                      : categoryFilter}
                  <span className={`dict-filter-arrow ${categoryFilterOpen ? "open" : ""}`}>▼</span>
                </button>

                {categoryFilterOpen && (
                  <div className="dict-filter-dropdown" role="listbox">
                    <button
                      type="button"
                      role="option"
                      className={`dict-filter-option ${!categoryFilter ? "selected" : ""}`}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setCategoryFilter(null);
                        setCategoryFilterOpen(false);
                      }}
                    >
                      Все категории
                    </button>
                    {hasUncategorized && (
                      <button
                        type="button"
                        role="option"
                        className={`dict-filter-option ${categoryFilter === "__none__" ? "selected" : ""}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setCategoryFilter("__none__");
                          setCategoryFilterOpen(false);
                        }}
                      >
                        Без категории
                      </button>
                    )}
                    {categoryFilterOptions.map((c) => (
                      <button
                        key={c}
                        type="button"
                        role="option"
                        className={`dict-filter-option ${categoryFilter === c ? "selected" : ""}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setCategoryFilter(c);
                          setCategoryFilterOpen(false);
                        }}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="dict-filter-label" ref={languageFilterRef}>
              <div className="dict-filter-wrap">
                <button
                  type="button"
                  className="dict-filter-select"
                  onClick={() => setLanguageFilterOpen((v) => !v)}
                  aria-expanded={languageFilterOpen}
                  aria-haspopup="listbox"
                  aria-label="Фильтр по языку слова"
                >
                  {!languageFilter
                    ? "Все языки"
                    : wordLanguageFilterLabel(languageFilter)}
                  <span className={`dict-filter-arrow ${languageFilterOpen ? "open" : ""}`}>▼</span>
                </button>

                {languageFilterOpen && (
                  <div className="dict-filter-dropdown" role="listbox">
                    <button
                      type="button"
                      role="option"
                      className={`dict-filter-option ${!languageFilter ? "selected" : ""}`}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setLanguageFilter(null);
                        setLanguageFilterOpen(false);
                      }}
                    >
                      Все языки
                    </button>
                    {languageFilterOptions.map((code) => (
                      <button
                        key={code}
                        type="button"
                        role="option"
                        className={`dict-filter-option ${languageFilter === code ? "selected" : ""}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setLanguageFilter(code);
                          setLanguageFilterOpen(false);
                        }}
                      >
                        {wordLanguageFilterLabel(code)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <button
              type="button"
              className="app-btn-outline"
              onClick={handleExportDocxClick}
              disabled={exporting || importing || filteredWords.length === 0}
            >
              {exporting ? "Экспорт..." : "Экспорт карточек"}
            </button>

            <input
              ref={dictionaryImportInputRef}
              type="file"
              accept=".txt,.csv,text/plain"
              className="dict-import-input-hidden"
              aria-hidden
              tabIndex={-1}
              onChange={handleDictionaryImportFile}
            />
            
            <button
              type="button"
              className="app-btn-outline"
              disabled={importing || loading}
              onClick={() => dictionaryImportInputRef.current?.click()}
              title="запятая или пробел"
            >
              {importing ? (importProgress ?? "Импорт...") : "Импорт из файла"}
            </button>

            <button type="button" className="app-btn-gradient" onClick={handleAdd} disabled={importing}>
              + Добавить слово
            </button>
          </div>
        </div>

        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16 }}>
            <div className="loading-dots" aria-hidden>
              <span /><span /><span />
            </div>
            <span className="app-muted">Загрузка...</span>
          </div>
        )}

        {importing && (
          <p className="app-muted" style={{ marginTop: 12 }} role="status" aria-live="polite">
            Импорт слов и генерация карточек: {importProgress ?? "подготовка..."}
          </p>
        )}

        {dictError && <p className="app-error" style={{ marginTop: 16 }}>{dictError}</p>}

        {decompositionInProgress && !loading && (
          <p className="app-muted dict-decomposition-banner" role="status" aria-live="polite" style={{ marginTop: 12 }}>
            Подождите, идёт декомпозиция слова...
          </p>
        )}

        {!loading && (
          <>
            <ul className="dict-word-list">
              {/* Нет слов */}
              {userWords.length === 0 && !dictError && (
                <li className="app-muted" style={{ padding: 24, textAlign: "center" }}>
                  Пока нет слов. Нажмите «Добавить слово» или «Импорт из файла».
                </li>
              )}
            
              {userWords.length > 0 && filteredWords.length === 0 && (
                <li className="app-muted" style={{ padding: 24, textAlign: "center" }}>
                  {languageFilter && categoryFilter
                    ? "Нет слов по выбранным фильтрам (категория и язык)."
                    : languageFilter
                      ? `Нет слов на языке «${wordLanguageFilterLabel(languageFilter)}».`
                      : categoryFilter === "__none__"
                        ? "Нет слов без категории."
                        : categoryFilter
                          ? `В категории «${categoryFilter}» нет слов.`
                          : "Нет подходящих слов."}
                </li>
              )}
          
              {filteredWords.map((entry) => (
                <WordCard
                  key={entry.id}
                  entry={entry}
                  decomposition={decompositionMap[entry.word] ?? (entry.parts?.length ? { parts: entry.parts } : null)}
                  decompositionLoading={Boolean(decompositionLoadingByWord[entry.word])}
                  menuOpen={menuOpenId === entry.id}
                  onToggleMenu={() => setMenuOpenId((id) => (id === entry.id ? null : entry.id))}
                  onEdit={() => handleEdit(entry)}
                  onDelete={() => handleDelete(entry)}
                  onToggleFavorite={() => handleToggleFavorite(entry)}
                  learningLinkBlocked={mnemoGenerating}
                />
              ))}
            </ul>
          </>
        )}
      </section>

      {modal === "add" && (
        <WordFormModal
          title="Добавить слово"
          initialWord=""
          initialTranslation=""
          initialTranscription=""
          initialCategory=""
          initialFavorite={false}
          initialWordLanguage={getStoredVerseLearningLang()}
          categories={allCategories}
          onSave={handleSaveAdd}
          onClose={() => setModal(null)}
          onClearError={() => setFormError(null)}
          error={formError}
          saving={saving}
        />
      )}

      {modal === "edit" && editingEntry && (
        <WordFormModal
          title="Редактировать слово"
          initialWord={editingEntry.word}
          initialTranslation={editingEntry.translation}
          initialTranscription={editingEntry.transcription ?? ""}
          initialCategory={editingEntry.category ?? ""}
          initialFavorite={editingEntry.is_favorite}
          initialWordLanguage={getStoredVerseLearningLang()}
          categories={allCategories}
          onSave={handleSaveEdit}
          onClose={() => { setModal(null); setEditingEntry(null); }}
          onClearError={() => setFormError(null)}
          error={formError}
          saving={saving}
        />
      )}
    </>
  );
}