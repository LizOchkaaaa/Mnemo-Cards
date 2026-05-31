// Файл для выбора моделей для генерации стихотворений

"use client";

import { useEffect, useState, type ChangeEvent } from "react";
import {
  DEFAULT_VERSE_PRESET_ID,
  getDefaultVerseGenerator,
  setDefaultVerseGenerator,
  VERSE_GENERATOR_OPTIONS,
  type VerseGeneratorChoice,
} from "@/lib/api";

type VerseGeneratorSelectProps = {
  className?: string;
  label?: string;         
};

// Компонент выбора модели для генерации стихотворений
export default function VerseGeneratorSelect({
  className = "",
  label = "Модель для стихотворения",
}: VerseGeneratorSelectProps) {
  // Текущее выбранное значение модели
  const [value, setValue] = useState<VerseGeneratorChoice>(DEFAULT_VERSE_PRESET_ID);

  useEffect(() => {
    // Получаем из localStorage ранее выбранную модель
    setValue(getDefaultVerseGenerator());
  }, []);

  // Обрабатываем изменения выбора
  function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    const v = e.target.value as VerseGeneratorChoice;
    // Проверяем, что выбранное значение существует
    if (VERSE_GENERATOR_OPTIONS.some((o) => o.value === v)) {
      // Сохраняем выбор в localStorage
      setDefaultVerseGenerator(v);
      // Обновляем состояние компонента
      setValue(v);
    }
  }

  return (
    <div className={className} style={{ marginBottom: 12 }}>
      <p className="app-section-title">Модели для генерации мнемонических стихотворений</p>
      <select
        id="verse-generator"
        value={
          VERSE_GENERATOR_OPTIONS.some((o) => o.value === value)
            ? value
            : VERSE_GENERATOR_OPTIONS[0]?.value ?? DEFAULT_VERSE_PRESET_ID
        }
        onChange={handleChange}
        aria-label={label}
      >
        {VERSE_GENERATOR_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
