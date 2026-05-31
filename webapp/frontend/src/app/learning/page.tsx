// Файл страницы настроек обучения

"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getDictionaryCategories,
  getDictionaryWords,
  useMnemoGenerationPending,
  type UserWord,
} from "@/lib/api";

// Фильтр языков
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

// Параметры
const MIN_QUESTIONS = 1;
const MAX_QUESTIONS = 10;
const MIN_TIME = 5;
const MAX_TIME = 60;

// Иконка документа
function IconDoc() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

// Иконка часов
function IconClock() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

// Иконка звёздочки
function IconStar() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  );
}

// Иконка категорий
function IconCategories() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="10" height="10" rx="2" />
      <circle cx="17" cy="7" r="5" />
      <rect x="2" y="12" width="10" height="10" rx="2" />
      <rect x="12" y="12" width="10" height="10" rx="2" />
    </svg>
  );
}

// Иконка глобуса
function IconGlobe() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a14.83 14.83 0 0 1 0 20M12 22a14.83 14.83 0 0 1 0-20" />
    </svg>
  );
}

// Переменные для хранения данных состояния страницы обучения
export default function LearningPage() {
  const router = useRouter(); 
  const mnemoGenerating = useMnemoGenerationPending();                                    // Навигация на страницу обучения
  const categoriesDropdownRef = useRef<HTMLDivElement>(null);                             // Ссылка на выпадающий список категорий
  const languageDropdownRef = useRef<HTMLDivElement>(null);                               // Список языков
  const [categoriesOpen, setCategoriesOpen] = useState(false);                            // Открыт/закрыт выпадающий список категорий
  const [languageOpen, setLanguageOpen] = useState(false);                                // Открыт/закрыт выпадающий список языков
  const [categoriesFromApi, setCategoriesFromApi] = useState<string[]>([]);               // Список категорий
  const [questionCount, setQuestionCount] = useState(10);                                 // Количество слов в обучении
  const [timePerWord, setTimePerWord] = useState(20);                                     // Время на ответ в секундах
  const [favoritesOnly, setFavoritesOnly] = useState(false);                              // Флаг "только избранные слова"
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());   // Выбранные категории
  const [customCategory, setCustomCategory] = useState("");                               // Поле для ввода своей категории
  const [languageFilter, setLanguageFilter] = useState<string | null>(null);              // Фильтр по языку
  const [dictionaryWords, setDictionaryWords] = useState<UserWord[]>([]);                 // Все слова
  const [wordsLoading, setWordsLoading] = useState(true);                                 // Подгрузка слов
  
  // Если пользователь кликнул вне
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (categoriesDropdownRef.current && !categoriesDropdownRef.current.contains(target)) setCategoriesOpen(false);
      if (languageDropdownRef.current && !languageDropdownRef.current.contains(target)) setLanguageOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Объединяем категории и пользовательские
  const allCategories = useMemo(
    () => Array.from(new Set([...DEFAULT_CATEGORIES, ...categoriesFromApi])),
    [categoriesFromApi]
  );

  const wordLanguageOptions = useMemo(() => {
    const codes = new Set(dictionaryWords.map((w) => normalizedWordLangCode(w)));
    const fromDict = [...codes].sort((a, b) => a.localeCompare(b));
    if (fromDict.length > 0) return fromDict;
    return Object.keys(WORD_LANGUAGE_LABELS).sort((a, b) => a.localeCompare(b));
  }, [dictionaryWords]);

  // Загружаем категории из словаря пользователя
  useEffect(() => {
    getDictionaryCategories()
      .then(setCategoriesFromApi)
      .catch(() => setCategoriesFromApi([]));
  }, []);

  useEffect(() => {
    setWordsLoading(true);
    getDictionaryWords()
      .then(setDictionaryWords)
      .catch(() => setDictionaryWords([]))
      .finally(() => setWordsLoading(false));
  }, []);

  // Фильтры
  const sessionFilteredWords = useMemo(() => {
    let filtered = [...dictionaryWords];
    if (favoritesOnly) filtered = filtered.filter((w) => w.is_favorite);
    const cats: string[] = Array.from(selectedCategories);
    const custom = customCategory.trim();
    if (custom) cats.push(custom);
    if (cats.length > 0) {
      filtered = filtered.filter((w) => w.category && cats.includes(w.category));
    }
    if (languageFilter) {
      filtered = filtered.filter((w) => normalizedWordLangCode(w) === languageFilter);
    }
    return filtered;
  }, [dictionaryWords, favoritesOnly, selectedCategories, customCategory, languageFilter]);

  // Можем обучаться
  const canStartLearning = !mnemoGenerating && !wordsLoading && sessionFilteredWords.length > 0;

  // Добавление/удаление категории
  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  // Переход на обучение с карточками с параметрами
  const handleStart = () => {
     if (mnemoGenerating) return;
     if (!canStartLearning) return;
     const params = new URLSearchParams();
    params.set("questions", String(questionCount));
    params.set("time", String(timePerWord));
    params.set("favorites", favoritesOnly ? "1" : "0");
    const cats: string[] = Array.from(selectedCategories);
    const custom = customCategory.trim();
    if (custom) {
      cats.push(custom);
    }
    if (cats.length > 0) {
      params.set("categories", cats.join(","));
    }
    if (languageFilter) {
      params.set("lang", languageFilter);
    }
    router.push(`/learning/run?${params.toString()}`);
  };

  return (
    <section className="glass glass-result glass-result--wide learning-settings">
      <h2 className="app-title">Настройки обучения</h2>
        {mnemoGenerating ? (
        <div className="learning-notice-banner learning-notice-banner--blocked" role="alert">
          <strong>Обучение недоступно</strong>
          <p className="learning-notice-banner__text">
            Пока генерируется карточка, начать обучение нельзя. Дождитесь окончания генерации
          </p>
        </div>
      ) : (
        <>
      <div className="learning-row">
        <div className="learning-row-label">
          <span className="learning-row-icon" aria-hidden><IconDoc /></span>
          <span>Количество слов</span>
        </div>
        <div className="learning-stepper">
          <button
            type="button"
            aria-label="Уменьшить"
            disabled={questionCount <= MIN_QUESTIONS}
            onClick={() => setQuestionCount((v) => Math.max(MIN_QUESTIONS, v - 1))}
          >
            −
          </button>
          <input
            type="number"
            min={MIN_QUESTIONS}
            max={MAX_QUESTIONS}
            value={questionCount}
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              if (!Number.isNaN(n)) setQuestionCount(Math.min(MAX_QUESTIONS, Math.max(MIN_QUESTIONS, n)));
            }}
            aria-label="Количество слов"
          />
          <button
            type="button"
            aria-label="Увеличить"
            disabled={questionCount >= MAX_QUESTIONS}
            onClick={() => setQuestionCount((v) => Math.min(MAX_QUESTIONS, v + 1))}
          >
            +
          </button>
        </div>
      </div>

      <div className="learning-row">
        <div className="learning-row-label">
          <span className="learning-row-icon" aria-hidden><IconClock /></span>
          <span>Время обучения на одно слово, сек</span>
        </div>
        <div className="learning-stepper">
          <button
            type="button"
            aria-label="Уменьшить"
            disabled={timePerWord <= MIN_TIME}
            onClick={() => setTimePerWord((v) => Math.max(MIN_TIME, v - 1))}
          >
            −
          </button>
          <input
            type="number"
            min={MIN_TIME}
            max={MAX_TIME}
            value={timePerWord}
            onChange={(e) => {
              const n = parseInt(e.target.value, 10);
              if (!Number.isNaN(n)) setTimePerWord(Math.min(MAX_TIME, Math.max(MIN_TIME, n)));
            }}
            aria-label="Секунд на слово"
          />
          <button
            type="button"
            aria-label="Увеличить"
            disabled={timePerWord >= MAX_TIME}
            onClick={() => setTimePerWord((v) => Math.min(MAX_TIME, v + 1))}
          >
            +
          </button>
        </div>
      </div>

      <div className="learning-row">
        <div className="learning-row-label">
          <span className="learning-row-icon" aria-hidden><IconStar /></span>
          <span>Только избранные карточки</span>
        </div>
        <button
          type="button"
          className={`learning-toggle ${favoritesOnly ? "active" : ""}`}
          onClick={() => setFavoritesOnly((v) => !v)}
          aria-pressed={favoritesOnly}
          aria-label="Только избранные карточки"
        />
      </div>

      <div className="learning-row">
        <div className="learning-row-label">
          <span className="learning-row-icon" aria-hidden><IconGlobe /></span>
          <span>Язык слов</span>
        </div>
        <div className="learning-dropdown" ref={languageDropdownRef} style={{ minWidth: 200 }}>
          <span className="learning-dropdown-field" aria-hidden>
            {languageFilter == null ? "Все языки" : wordLanguageFilterLabel(languageFilter)}
          </span>
          <button
            type="button"
            className={`learning-dropdown-arrow ${languageOpen ? "open" : ""}`}
            onClick={() => setLanguageOpen((v) => !v)}
            aria-label="Выбрать язык слов"
            aria-expanded={languageOpen}
            aria-haspopup="listbox"
          >
            ▼
          </button>
          {languageOpen && (
            <div className="learning-dropdown-list" role="listbox">
              <button
                type="button"
                role="option"
                className={languageFilter == null ? "selected" : ""}
                aria-selected={languageFilter == null}
                onClick={() => {
                  setLanguageFilter(null);
                  setLanguageOpen(false);
                }}
              >
                Все языки
              </button>
              {wordLanguageOptions.map((code) => (
                <button
                  key={code}
                  type="button"
                  role="option"
                  className={languageFilter === code ? "selected" : ""}
                  aria-selected={languageFilter === code}
                  onClick={() => {
                    setLanguageFilter(code);
                    setLanguageOpen(false);
                  }}
                >
                  {wordLanguageFilterLabel(code)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

       <div className="learning-row">
        <div className="learning-row-label">
          <span className="learning-row-icon" aria-hidden><IconCategories /></span>
          <span>Категории слов</span>
        </div>
        <div className="learning-dropdown" ref={categoriesDropdownRef} style={{ minWidth: 200 }}>
          <span className="learning-dropdown-field" aria-hidden>
            {selectedCategories.size === 0
              ? "Все категории"
              : selectedCategories.size === allCategories.length
                ? "Все выбраны"
                : `Выбрано: ${selectedCategories.size}`}
          </span>
          <button
            type="button"
            className={`learning-dropdown-arrow ${categoriesOpen ? "open" : ""}`}
            onClick={() => setCategoriesOpen((v) => !v)}
            aria-label="Открыть список категорий"
            aria-expanded={categoriesOpen}
            aria-haspopup="listbox"
          >
            ▼
          </button>
          {categoriesOpen && (
            <div className="learning-categories-list" role="listbox">
              <p className="learning-categories-hint">Если ни одна не выбрана — участвуют все.</p>
              {allCategories.map((cat) => (
                <label key={cat}>
                  <input
                    type="checkbox"
                    checked={selectedCategories.has(cat)}
                    onChange={() => toggleCategory(cat)}
                  />
                  <span>{cat}</span>
                </label>
              ))}
              {selectedCategories.has("Другое") && (
                <div style={{ marginTop: 12 }}>
                  <p className="learning-categories-hint" style={{ marginBottom: 4 }}>
                    Своя категория (будут выбраны слова с такой категорией):
                  </p>
                  <input
                    type="text"
                    value={customCategory}
                    onChange={(e) => setCustomCategory(e.target.value)}
                    placeholder="Например: Путешествия"
                    className="learning-categories-input"
                  />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 28, display: "flex", justifyContent: "center" }}>
        <button
          type="button"
          className="app-btn-gradient"
          onClick={handleStart}
          disabled={!canStartLearning}
          title={
            !canStartLearning
              ? mnemoGenerating
                ? "Идёт генерация карточки"
                : sessionFilteredWords.length === 0
                  ? "Нет слов по выбранным фильтрам"
                  : undefined
              : undefined
          }
        >
          Начать обучение
        </button>
      </div>
      </>
      )}
    </section>
  );
}
