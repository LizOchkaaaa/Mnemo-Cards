//  Файл для хранения URL аватара пользователя

"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

// Ключ для хранения URL аватара в localStorage
const STORAGE_KEY = "mnemo_avatar_url";

type AvatarContextValue = {
  avatarUrl: string | null;
  setAvatarUrl: (url: string | null) => void; // Функция для обновления аватара
};

// Создаём контекст для хранения данных аватара
const AvatarContext = createContext<AvatarContextValue | null>(null);

// Компонент-обёртка для глобального доступа к аватару пользователя
export function AvatarProvider({
  children,
  initialAvatarUrl,
}: {
  children: React.ReactNode;
  initialAvatarUrl?: string | null;
}) {
  // Храним URL аватара
  const [avatarUrl, setAvatarUrlState] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    // Есть данные от сервера
    if (initialAvatarUrl !== undefined) {
      // Сохраняем в localStorage
      if (initialAvatarUrl) localStorage.setItem(STORAGE_KEY, initialAvatarUrl);
      else localStorage.removeItem(STORAGE_KEY);
      return initialAvatarUrl;
    }
    
    // Кэш браузера
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored || null;
  });

  // Обновленный аватар при повторной загрузке данных пользователя
  useEffect(() => {
    // Если нет новых данных от бэкенда, то ничего не делаем
    if (initialAvatarUrl === undefined) return;
    // Обновляем состояние с новым URL аватара
    setAvatarUrlState(initialAvatarUrl);
    // Синхронизируем localStorage 
    if (typeof window !== "undefined") {
      if (initialAvatarUrl) localStorage.setItem(STORAGE_KEY, initialAvatarUrl);
      else localStorage.removeItem(STORAGE_KEY);
    }
  }, [initialAvatarUrl]);

  // Обновляем аватар из любого компонента
  const setAvatarUrl = useCallback((url: string | null) => {
    // Обновляем состояние
    setAvatarUrlState(url);
    // Синхронизируем localStorage
    if (typeof window !== "undefined") {
      if (url) localStorage.setItem(STORAGE_KEY, url);
      else localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return (
    <AvatarContext.Provider value={{ avatarUrl, setAvatarUrl }}>
      {children}
    </AvatarContext.Provider>
  );
}

// Функция получения доступа к аватару
export function useAvatar() {
  // Получаем значение контекста
  const ctx = useContext(AvatarContext);
  // Если контекст не найден, то ошибка
  if (!ctx) throw new Error("Download avatar");
  return ctx;
}