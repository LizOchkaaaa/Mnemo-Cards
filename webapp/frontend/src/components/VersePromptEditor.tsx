// Файл для выбора изучаемого языка

"use client";

import { useEffect, useState } from "react";
import {
  getStoredVerseLearningLang,
  setStoredVerseLearningLang,
  type VerseLearningLanguage,
} from "@/lib/api";

// Список языков для изучения
const LANG_OPTIONS: { id: VerseLearningLanguage; label: string }[] = [
  { id: "en", label: "Английский" },
  { id: "de", label: "Немецкий" },
  { id: "fr", label: "Французский" },
  { id: "es", label: "Испанский" },
  { id: "it", label: "Итальянский" },
];

// Компонент выбора изучаемого языка
export default function VersePromptEditor() {
  // Текущий выбранный язык (по умолчанию английский)
  const [lang, setLang] = useState<VerseLearningLanguage>("en");

  useEffect(() => {
    // Получаем сохранённое значение из localStorage
    const savedLang = getStoredVerseLearningLang();
    setLang(savedLang);
  }, []);

  // Обрабатываем изменения выбранного языка
  function handleChange(next: VerseLearningLanguage) {
    setLang(next);                       // Обновляем UI
    setStoredVerseLearningLang(next);    // Сохраняем в localStorage
  }

  return (
    <div style={{ marginTop: 20 }}>
      <p className="app-section-title">Изучаемый язык</p>
      <select
        value={lang}
        onChange={(e) => handleChange(e.target.value as VerseLearningLanguage)}
        aria-label="Изучаемый язык"
        style={{ marginTop: 6 }}
      >
        {LANG_OPTIONS.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}