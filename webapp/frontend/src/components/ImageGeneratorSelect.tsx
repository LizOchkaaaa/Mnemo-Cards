// Файл выбора модели для генерации изображения

"use client";

import { useEffect, useState, type ChangeEvent } from "react";
import {
  DEFAULT_IMAGE_GENERATOR_ID,
  getDefaultImageGenerator,
  IMAGE_GENERATOR_OPTIONS,
  setDefaultImageGenerator,
  type ImageGeneratorChoice,
} from "@/lib/api";

type ImageGeneratorSelectProps = {
  className?: string;   
  label?: string;
};

// Компонент выбора модели для генерации изображений
export default function ImageGeneratorSelect({
  className = "",
  label = "Генератор изображений",
}: ImageGeneratorSelectProps) {
  // Текущее выбранное значение модели
  const [value, setValue] = useState<ImageGeneratorChoice>(DEFAULT_IMAGE_GENERATOR_ID);

  useEffect(() => {
    // Получаем из localStorage ранее выбранную модель
    setValue(getDefaultImageGenerator());
  }, []);

  // Обрабатываем изменения выбора
  function handleChange(e: ChangeEvent<HTMLSelectElement>) {
    const v = e.target.value as ImageGeneratorChoice;
    if (IMAGE_GENERATOR_OPTIONS.some((o) => o.value === v)) {
      setDefaultImageGenerator(v);
      setValue(v);
    }
  }

  return (
    <div className={className} style={{ marginBottom: 12 }}>
      <p className="app-section-title">Модели для генерации мнемонических изображений</p>
      <select
        id="image-generator"
        value={
          IMAGE_GENERATOR_OPTIONS.some((o) => o.value === value)
            ? value
            : IMAGE_GENERATOR_OPTIONS[0]?.value ?? DEFAULT_IMAGE_GENERATOR_ID
        }
        onChange={handleChange}
        aria-label={label}
      >
        {IMAGE_GENERATOR_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
