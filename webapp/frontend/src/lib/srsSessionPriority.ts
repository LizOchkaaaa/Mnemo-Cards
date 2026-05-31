// Файл для формирования очереди карточек для сессии: чем выше срочность, тем раньше показывается

import type { UserWord } from "@/lib/api";

// Извлекаем дату следующего повторения
function parseSrsNextReviewMs(w: UserWord, fallbackMs: number): number {
  // Получаем строковое значение даты следующего повторения
  const raw = w.srs_next_review_at;
  // Если даты нет или это пустая строка, то значение по умолчанию
  if (raw == null || raw === "") return fallbackMs;
  // Преобразуем строку в timestamp
  const t = Date.parse(raw);
  // Если дата некорректна, возвращаем значение по умолчанию
  return Number.isNaN(t) ? fallbackMs : t;
}

// Вычисляем срочность повторения слова, чем больше число, тем выше приоритет
export function srsSessionUrgencyMs(w: UserWord, nowMs: number): number {
  // Получаем timestamp следующего повторения
  const nextReviewMs = parseSrsNextReviewMs(w, nowMs);
  // Формула срочности
  return nowMs - nextReviewMs;
}

// Слова, которые пора повторять
export function filterWordsDueForLesson(
  words: UserWord[],  
  nowMs: number = Date.now()
): UserWord[] {
  return words.filter((w) => {
    // Получаем значение следующей даты повторения
    const raw = w.srs_next_review_at;
    // Если значение отсутствует, то слово пора повторять
    if (raw == null || raw === "") return true;
    const t = Date.parse(raw);
    // Если дата невалидна, то считаем слово просроченным 
    if (Number.isNaN(t)) return true;
    // Возвращаем true, если дата повторения меньше или равна текущему времени
    return t <= nowMs;
    
  });
}

// Порядок слов для обучения:
export function sortWordsBySrsSessionPriority(
  words: UserWord[], 
  nowMs: number = Date.now()
): UserWord[] {
  // Создаём копию массива и сортируем
  return [...words].sort((a, b) => {
    // Вычисляем срочность для слов
    const ua = srsSessionUrgencyMs(a, nowMs);
    const ub = srsSessionUrgencyMs(b, nowMs);
    // Сравниваем
    if (ub !== ua) return ub - ua;
    // Если срочность одинаковая, то сортируем по ID слова
    return a.id - b.id;
  });
}