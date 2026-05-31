// Файл для импорта слов в словарь

export type DictionaryImportPair = { word: string; translation: string };

// Преобразуем текст словаря в массив пар "слово - перевод"
export function parseDictionaryImportText(text: string): DictionaryImportPair[] {
  // Удаляем BOM в начале файла
  const normalized = text.replace(/^\uFEFF/, "");
  // Разбиваем текст на строки
  const lines = normalized.split(/\r?\n/);
  // Формируем массив
  const out: DictionaryImportPair[] = [];

  for (const line of lines) {
    // Удаляем начальные и конечные пробелы
    const trimmed = line.trim();
    // Пропускаем пустые строки и комментарии
    if (!trimmed || trimmed.startsWith("#")) continue;

    let word: string;        // Слово
    let translation: string; // Перевод

    // Разделитель -
    if (trimmed.includes("-")) {
      const i = trimmed.indexOf("-");
      word = trimmed.slice(0, i).trim();
      translation = trimmed.slice(i + 1).trim();
    }
    
    // Разделитель пробел
    else {
      const m = trimmed.match(/^(\S+)\s+(.+)$/);
      // Если строка не соответствует паттерну, пропуск
      if (!m) continue;
      word = m[1].trim();    
      translation = m[2].trim();
    }

    // Добавляем пару только если оба поля не пустые
    if (word.length > 0 && translation.length > 0) {
      out.push({ word, translation });
    }
  }

  return out;
}