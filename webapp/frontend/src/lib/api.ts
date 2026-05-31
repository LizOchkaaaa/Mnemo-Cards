// Главный клиентский файл запросов

"use client";

import { useEffect, useState } from "react";

// JWT токен
const AUTH_TOKEN_KEY = "mnemo_token";
// Таймаут запросов (45 сек)
const REQUEST_TIMEOUT_MS = 45_000;
// Таймаут генерации мнемоники (3 мин)
const MNEMO_GENERATE_TIMEOUT_MS = 180_000;
// Выбранная модель генерации стихотворений
const VERSE_GENERATOR_KEY = "mnemo_verse_generator";
// Язык изучения
const VERSE_LEARNING_LANG_KEY = "mnemo_verse_learning_language";
// Выбранная модель генерации изображений
const IMAGE_GENERATOR_KEY = "mnemo_image_generator";

// Начало генерации
export const MNEMO_GENERATION_START_EVENT = "mnemo:generation-start";
// Конец генерации
export const MNEMO_GENERATION_END_EVENT = "mnemo:generation-end";
// Успешная генерация
export const MNEMO_GENERATION_SUCCESS_EVENT = "mnemo:generation-success";
// Счётчик активных генераций мнемоники
let mnemoGenerationDepth = 0;

// Изучаемый язык
export type VerseLearningLanguage = "en" | "de" | "es" | "it" | "fr";

const VERSE_LEARNING_ALLOWED: readonly VerseLearningLanguage[] = [
  "en",
  "de",
  "es",
  "it",
  "fr",
];

// Проверка, идёт ли сейчас генерация мнемоники
export function isMnemoGenerationPendingSync(): boolean {
  return mnemoGenerationDepth > 0;
}

// Модели стихотворений
export const FALLBACK_VERSE_PRESETS = [
  { id: "gptunnel:gpt-5.4", label: "GPTunnel — gpt-5.4" },
  { id: "chad:gemini-3-flash", label: "Chad — Gemini 3 Flash" },
  { id: "yandex:deepseek-v32/latest", label: "Yandex Cloud — DeepSeek V3.2" },
] as const;

export type VerseGeneratorChoice = (typeof FALLBACK_VERSE_PRESETS)[number]["id"];

// Значение по умолчанию для стихотворений
export const DEFAULT_VERSE_PRESET_ID: VerseGeneratorChoice = "gptunnel:gpt-5.4";

export const VERSE_GENERATOR_OPTIONS: { value: VerseGeneratorChoice; label: string }[] =
  FALLBACK_VERSE_PRESETS.map((p) => ({ value: p.id, label: p.label }));

// Модели изображений 
export const IMAGE_GENERATOR_OPTIONS = [
  { value: "black-forest-labs/FLUX.1-schnell", label: "FLUX.1 (RuGPT)" },
  { value: "grok-imagine-text-to-image", label: "Grok (MashaGPT)" },
  { value: "deepai-text2img", label: "DeepAI text2img" },
] as const;

export type ImageGeneratorChoice = (typeof IMAGE_GENERATOR_OPTIONS)[number]["value"];

// Значение по умолчанию для изображений
export const DEFAULT_IMAGE_GENERATOR_ID: ImageGeneratorChoice = "black-forest-labs/FLUX.1-schnell";

// Запрос на генерацию мнемоники
export type GenerateMnemoRequest = {
  word: string;                                    // Слово
  translation: string;                             // Перевод
  parts?: string[];                                // Декомпозиция
  consonance?: string;                             // Варианты рифмовок
  verse_generator?: VerseGeneratorChoice;          // Выбранная модель для стихотворения
  image_generator?: ImageGeneratorChoice;          // Выбранная модель для изображения
  verse_learning_language?: VerseLearningLanguage; // Изучаемый язык
};

// Ответ
export type MnemoResponse = {
  mnemonic_phrase_ru: string;      // Стихотворение
  image_prompt?: string | null;    // Промпт для генерации изображения
  image_url?: string | null;       // URL сгенерированного изображения
  verse_source: string;            // Какая модель генерировала
  cache_hit: boolean;              // Был ли ответ взят из кэша
};

// Данные пользователя
export type UserInfo = {
  email: string;
  username: string | null;
  avatar_url?: string | null;
};

// Ответ аутентификации
export type AuthResponse = {
  access_token: string;   // JWT токен доступа
  token_type: string;     // Тип токена
  user: UserInfo;         // Данные пользователя
};

// Структура ошибки API
type ApiErrorPayload = {
  detail?: string;   // Описание ошибки
  message?: string;  // Сообщение об ошибке
};

// Функция для всех запросов от клиента к серверу
async function requestJson<T>(
  path: string,                             // Путь
  init?: RequestInit,                       // Опции
  timeoutMs: number = REQUEST_TIMEOUT_MS    // Таймаут
): Promise<T> {
  // Создаём AbortController для возможности отмены запроса по таймауту
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // Получаем токен, если пользователь авторизован
  const token = getStoredToken();
  
  // Формируем заголовки
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> ?? {})
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(path, {
      ...init,
      headers,
      signal: controller.signal  // Привязываем сигнал для отмены
    });

    // Если статус не 2xx, то ошибка
    if (!response.ok) {
      throw new Error(await parseError(response));
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timed out");
    }
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Network error");
  } finally {
    clearTimeout(timeoutId);  // Очищаем таймаут
  }
}

// Регистрация пользователя
export async function register(email: string, password: string, username?: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, username: username || null })
  });
}

// Авторизация пользователя
export async function login(email: string, password: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password })
  });
}

// Получение данных текущего пользователя по токену
export async function getMe(): Promise<UserInfo> {
  return requestJson<UserInfo>("/api/v1/auth/me");
}

// Данные для обновления профиля
export type UpdateProfileData = {
  username?: string | null;
  email?: string | null;
  password?: string;
  avatar_url?: string | null;
};

// Обновление профиля пользователя
export async function updateProfile(data: UpdateProfileData): Promise<UserInfo> {
  return requestJson<UserInfo>("/api/v1/auth/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// Загрузка фото профиля
export async function uploadAvatarPhoto(file: File): Promise<UserInfo> {
  const token = getStoredToken();
  if (!token) throw new Error("Not authenticated");
  const form = new FormData();
  form.append("file", file);
  
  const res = await fetch("/api/v1/auth/me/avatar", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  
  
  if (!res.ok) {
    const text = await res.text();
    let msg = text;
    try {
      const j = JSON.parse(text) as { detail?: string };
      if (j.detail) msg = j.detail;
    } catch {
      // Если не JSON, оставляем исходный текст
    }
    throw new Error(msg);
  }
  return res.json() as Promise<UserInfo>;
}

// Структура слова пользователя
export type UserWord = {
  id: number;
  word: string;                       // Слово
  translation: string;                // Перевод
  transcription: string | null;       // Транскрипция IPA
  category: string | null;            // Категория
  word_language?: string;             // Язык
  is_favorite: boolean;               // В избранном?
  is_learned?: boolean;               // Выучено ли слово?
  parts?: string[] | null;            // Декомпозиция
  srs_easiness?: number | null;       // Фактор лёгкости
  srs_interval_days?: number | null;  // Интервал до следующего повторения в днях
  srs_repetitions?: number | null;    // Количество успешных повторений
  srs_next_review_at?: string | null; // Дата следующего повторения
};

// Проверка, есть ли у слова разбор
export function wordHasDecomposition(w: UserWord): boolean {
  const p = w.parts;
  if (!Array.isArray(p) || p.length === 0) return false;
  return p.some((x) => String(x ?? "").trim().length > 0);
}

// Получение всех слов пользователя из словаря
export async function getDictionaryWords(): Promise<UserWord[]> {
  return requestJson<UserWord[]>("/api/v1/dictionary/words");
}

// Получение слов, у которых наступило время повторения
export async function getDictionaryWordsDue(): Promise<UserWord[]> {
  return requestJson<UserWord[]>("/api/v1/dictionary/words/due");
}

// Передача оценки и id карточки для SM-2 алгоритма
export async function submitSrsReview(
  entryId: number,
  quality: number
): Promise<UserWord> {
  return requestJson<UserWord>(`/api/v1/dictionary/words/${entryId}/srs-review`, {
    method: "POST",
    body: JSON.stringify({ quality }),
  });
}

// Получение списка всех категорий из словаря пользователя
export async function getDictionaryCategories(): Promise<string[]> {
  return requestJson<string[]>("/api/v1/dictionary/categories");
}

// Тип для статистики обучения
export type LearningStats = {
  days_learning: number;   // Сколько дней учится пользователь
  words_total: number;     // Всего слов в словаре
  words_learned: number;   // Выучено слов
};

// Получение статистики обучения
export async function getLearningStats(): Promise<LearningStats> {
  return requestJson<LearningStats>("/api/v1/dictionary/stats");
}

// Чтение JWT-токена из localStorage
export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

// Сохранение JWT-токена после входа/регистрации
export function setStoredToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

// Полная очистка токена при выходе
export function clearStoredToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(AUTH_TOKEN_KEY);
}

// Обработка ошибок
async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorPayload;
    if (payload?.detail) return payload.detail;
    if (payload?.message) return payload.message;
  } catch {
  }
  return `Request failed with status ${response.status}`;
}

// Структура ответа состояния сервисов
export type VersePresetDto = {
  id: string;          // Идентификатор
  label: string;       // Название
  provider?: string;   // Провайдер
  model?: string;      // Модель
};

// Структура запроса
export type HealthResponse = {
  status: string;                                                               // Статус сервера
  providers: Record<string, boolean>;                                           // Какие провайдеры доступны
  mnemo_models?: Record<string, string>;                                        // Доступные модели
  verse_presets?: VersePresetDto[];                                             // Доступные пресеты стихов
  verse_prompt_template_default?: string;                                       // Шаблон промпта для стихотворений
  verse_prompt_templates?: Record<string, string>;                              // Шаблоны по языку (en, de)
  verse_learning_languages?: { id: string; label: string; active?: boolean }[]; // Доступные языки
};

// Проверка состояния сервера
export async function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/v1/health");
}

// Чтение выбранной модели стихотворений из localStorage
export function getDefaultVerseGenerator(): VerseGeneratorChoice {
  if (typeof window === "undefined") return DEFAULT_VERSE_PRESET_ID;
  const v = localStorage.getItem(VERSE_GENERATOR_KEY);
  if (!v) return DEFAULT_VERSE_PRESET_ID;
  if (v) return v as VerseGeneratorChoice;
  return DEFAULT_VERSE_PRESET_ID;
}

// Сохранение выбранной модели пользователем
export function setDefaultVerseGenerator(value: VerseGeneratorChoice): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(VERSE_GENERATOR_KEY, value);
}

// Проверка на язык
function isVerseLearningLanguage(v: string): v is VerseLearningLanguage {
  return (VERSE_LEARNING_ALLOWED as readonly string[]).includes(v);
}

// Чтение выбранного языка изучения
export function getStoredVerseLearningLang(): VerseLearningLanguage {
  if (typeof window === "undefined") return "en";
  const v = localStorage.getItem(VERSE_LEARNING_LANG_KEY);
  if (v && isVerseLearningLanguage(v)) return v;
  return "en";
}

// Сохранение выбранного языка изучения
export function setStoredVerseLearningLang(lang: VerseLearningLanguage): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(VERSE_LEARNING_LANG_KEY, lang);
}

// Чтение выбранной модели изображений из localStorage
export function getDefaultImageGenerator(): ImageGeneratorChoice {
  if (typeof window === "undefined") return DEFAULT_IMAGE_GENERATOR_ID;
  const v = localStorage.getItem(IMAGE_GENERATOR_KEY);
  if (v) return v as ImageGeneratorChoice;
  return DEFAULT_IMAGE_GENERATOR_ID;
}

// Сохранение выбранной модели изображений пользователем
export function setDefaultImageGenerator(value: ImageGeneratorChoice): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(IMAGE_GENERATOR_KEY, value);
}

// Структура ответа декомпозиции слова
export type DecompositionResponse = {
  word: string;              // Исходное слово
  translation_ru: string;    // Перевод
  parts: string[];           // Разбор на части
};

// Запрос на декомпозицию слова
export async function getDecomposition(
  word: string,
  translation: string,
  lang: string = "en"
): Promise<DecompositionResponse> {
  const ll = (lang || "en").trim().toLowerCase().slice(0, 8) || "en";
  const base = `word=${encodeURIComponent(word)}&translation=${encodeURIComponent(translation)}`;
  const q = ll === "en" ? base : `${base}&lang=${encodeURIComponent(ll)}`;
  return requestJson<DecompositionResponse>(`/api/v1/dictionary/decompose?${q}`);
}


// Получение автоматической транскрипции слова
export async function getTranscription(
  word: string,
  lang: string = "en"
): Promise<string> {
  const w = word.trim();
  const ll = (lang || "en").trim().toLowerCase().slice(0, 8) || "en";
  if (!w) return "";
  try {
    const q =
      ll === "en"
        ? `?word=${encodeURIComponent(w)}`
        : `?word=${encodeURIComponent(w)}&lang=${encodeURIComponent(ll)}`;
    const res = await requestJson<{ transcription: string }>(`/api/v1/dictionary/transcription${q}`);
    return (res.transcription ?? "").trim();
  } catch {
    return "";
  }
}

// Автоматический перевод через MyMemory
export async function getTranslation(
  word: string,
  options?: { sourceLang?: string; targetLang?: string }
): Promise<string> {
  const w = word.trim();
  const sl = (options?.sourceLang ?? "en").trim().toLowerCase().slice(0, 8) || "en";
  const tl = (options?.targetLang ?? "ru").trim().toLowerCase().slice(0, 8) || "ru";
  if (!w) return "";
  try {
    const q = `?word=${encodeURIComponent(w)}&source_lang=${encodeURIComponent(sl)}&target_lang=${encodeURIComponent(tl)}`;
    const res = await requestJson<{ translation: string }>(`/api/v1/dictionary/translation${q}`);
    return (res.translation ?? "").trim();
  } catch {
    return "";
  }
}

// Автоперевод слова
export function getAutoTranslationLangPair(wordStudyLang: string): {
  sourceLang: string;
  targetLang: string;
} {
  const s = (wordStudyLang || "en").trim().toLowerCase().slice(0, 8) || "en";
  if (s === "ru") return { sourceLang: "ru", targetLang: "en" };
  return { sourceLang: s, targetLang: "ru" };
}

// Подбор языка по символам
export function guessPronunciationLang(word: string): string {
  const w = word.trim();
  if (!w) return "en";
  if (/[\u3040-\u30ff]/.test(w)) return "ja";
  if (/[\uac00-\ud7a3]/.test(w)) return "ko";
  if (/[\u4e00-\u9fff]/.test(w)) return "zh";
  if (/[äöüÄÖÜß]/.test(w)) return "de";
  if (/ñ/.test(w)) return "es";
  if (/[ãõ]/.test(w)) return "pt";
  if (/[àâäæéèêëïîôùûüÿœç]/i.test(w)) return "fr";
  return "en";
}

// Преобразуем ISO 639-1 код языка в BCP 47 код
export function pronunciationLangToWebSpeech(iso639: string): string {
  const code = iso639.trim().toLowerCase().slice(0, 2);
  const m: Record<string, string> = {
    en: "en-US",
    ru: "ru-RU",
    de: "de-DE",
    fr: "fr-FR",
    es: "es-ES",
    it: "it-IT",
    pt: "pt-PT",
    zh: "zh-CN",
    ja: "ja-JP",
    ko: "ko-KR",
  };
  return m[code] ?? "en-US";
}

// URL воспроизведения
export async function getPronunciation(
  word: string,
  options?: { lang?: string }
): Promise<string | null> {
  const w = word.trim();
  if (!w) return null;
  const langIso = (options?.lang ?? guessPronunciationLang(w)).trim().toLowerCase().slice(0, 8);
  try {
    const q = `?word=${encodeURIComponent(w)}&lang=${encodeURIComponent(langIso)}`;
    const res = await requestJson<{ audio_url: string }>(
      `/api/v1/dictionary/pronunciation${q}`
    );
    const raw = (res.audio_url ?? "").trim();
    return raw || null;
  } catch {
    return null;
  }
}

// Добавление нового слова в словарь
export async function addDictionaryWord(
  word: string,
  translation: string,
  options?: {
    is_favorite?: boolean;
    category?: string | null;
    transcription?: string | null;
    word_language?: string | null;
  }
): Promise<UserWord> {
  return requestJson<UserWord>("/api/v1/dictionary/words", {
    method: "POST",
    body: JSON.stringify({
      word,
      translation,
      is_favorite: options?.is_favorite ?? false,
      category: options?.category ?? null,
      transcription: options?.transcription ?? null,
      word_language: options?.word_language ?? "en",
    }),
  });
}

// Обновление существующей записи в словаре
export async function updateDictionaryWord(
  id: number,
  data: {
    word?: string;
    translation?: string;
    is_favorite?: boolean;
    is_learned?: boolean;
    category?: string | null;
    transcription?: string | null;
    word_language?: string | null;
  }
): Promise<UserWord> {
  return requestJson<UserWord>(`/api/v1/dictionary/words/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// Удаление слова из словаря
export async function deleteDictionaryWord(id: number): Promise<void> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`/api/v1/dictionary/words/${id}`, { method: "DELETE", headers });
  if (!res.ok) {
    const payload = await res.json().catch(() => null) as ApiErrorPayload | null;
    throw new Error(payload?.detail || payload?.message || `Request failed with status ${res.status}`);
  }
}

// Запрос генерации мнемокарточки
export async function generateMnemo(payload: GenerateMnemoRequest): Promise<MnemoResponse> {
  // Генератор стихов
  const verse_generator = payload.verse_generator ?? getDefaultVerseGenerator();
  // Генератор изображений
  const image_generator = payload.image_generator ?? getDefaultImageGenerator();
  // Язык
  const verse_learning_language = payload.verse_learning_language ?? getStoredVerseLearningLang();

  const body: GenerateMnemoRequest = {
    ...payload,   
    verse_generator,           
    image_generator,              
    verse_learning_language,     
  };

  if (typeof window !== "undefined") {
    mnemoGenerationDepth += 1;
    window.dispatchEvent(new CustomEvent(MNEMO_GENERATION_START_EVENT));
  }

  try {
    // Отправляем POST-запрос
    const result = await requestJson<MnemoResponse>(
      "/api/v1/mnemo/generate",                    
      { method: "POST", body: JSON.stringify(body) }, 
      MNEMO_GENERATE_TIMEOUT_MS    
    );

    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent(MNEMO_GENERATION_SUCCESS_EVENT, { 
          detail: { word: payload.word }
        })
      );
    }
    
    return result;  
  } finally {
    if (typeof window !== "undefined") {
      // Уменьшаем счётчик активных генераций
      mnemoGenerationDepth = Math.max(0, mnemoGenerationDepth - 1);
      window.dispatchEvent(new CustomEvent(MNEMO_GENERATION_END_EVENT));
    }
  }
}

// Получение уже сохранённой мнемоники для конкретного слова
export async function getCachedMnemo(word: string): Promise<MnemoResponse> {
  return requestJson<MnemoResponse>(`/api/v1/mnemo/cache/${encodeURIComponent(word)}`);
}

// Путь для изображения
export function resolveImageUrl(imageUrl?: string | null): string | null {
  if (!imageUrl) return null;
  if (imageUrl.startsWith("http://") || imageUrl.startsWith("https://")) {
    return imageUrl;
  }
  return imageUrl.startsWith("/") ? imageUrl : `/${imageUrl}`;
}

// Экспорт выбранных слов в DOCX
export async function exportCardsToDocx(entryIds: number[]): Promise<void> {
  if (entryIds.length === 0) return;
  const token = getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch("/api/v1/dictionary/export/docx", {
    method: "POST",
    headers,
    body: JSON.stringify({ entry_ids: entryIds }),
  });

  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const data = await res.json() as { detail?: unknown };
      if (data?.detail != null) detail = String(data.detail);
    } catch {
      detail = `${res.status}`;
    }
    throw new Error(detail || "Ошибка экспорта DOCX");
  }

  const blob = await res.blob();
  const cd = res.headers.get("Content-Disposition");
  let fname = "mnemo-cards.docx";
  const m = cd?.match(/filename="?([^";\n]+)"?/i);
  if (m?.[1]?.trim()) fname = m[1].trim();

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fname;
  a.click();
  URL.revokeObjectURL(url);
}

// Состояние генерации мнемокаточки
export function useMnemoGenerationPending(): boolean {
  const [pending, setPending] = useState(() =>
    typeof window !== "undefined" ? isMnemoGenerationPendingSync() : false        
  );

  useEffect(() => {
    setPending(isMnemoGenerationPendingSync());
    const sync = () => setPending(isMnemoGenerationPendingSync());
    window.addEventListener(MNEMO_GENERATION_START_EVENT, sync);
    window.addEventListener(MNEMO_GENERATION_END_EVENT, sync);
  
    return () => {
      window.removeEventListener(MNEMO_GENERATION_START_EVENT, sync);
      window.removeEventListener(MNEMO_GENERATION_END_EVENT, sync);
    };
  }, []);
  return pending;
}