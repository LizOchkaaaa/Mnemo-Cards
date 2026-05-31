// Файл для проверки JWT-токена, загрузки данных пользователя

"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import AppShell from "./AppShell";
import { AvatarProvider } from "../contexts/AvatarContext";
import { clearStoredToken, getMe, getStoredToken, type UserInfo } from "../lib/api";
import {
  MNEMO_GENERATION_END_EVENT,
  MNEMO_GENERATION_START_EVENT,
  MNEMO_GENERATION_SUCCESS_EVENT,
} from "../lib/api";

// Главный компонент-обертка для всех страниц
export default function AppLayoutWrapper({ children }: { children: React.ReactNode }) {
  // Текущий URL
  const pathname = usePathname();
  // Для перехода на страницу
  const router = useRouter();
  // Данные пользователя
  const [user, setUser] = useState<UserInfo | null>(null);
  // Флаг готовности
  const [ready, setReady] = useState(false);
  // Проверка идёт ли генерация
  const [globalMnemoGenerating, setGlobalMnemoGenerating] = useState(false);
  // Показываем уведомление
  const [globalMnemoReadyToast, setGlobalMnemoReadyToast] = useState(false);
  // Счётчик активных генераций
  const activeGenerationsRef = useRef(0);
  // Таймер для автоматического скрытия уведомления
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Проверяем, находимся ли на странице входа
  const isLoginPage = pathname === "/";

  // Проверка авторизации и загрузки данных пользователя
  useEffect(() => {
    if (isLoginPage) {
      setReady(true);
      return;
    }

    // Проверяем наличие токена
    const token = getStoredToken();
    if (!token) {
      // Отправляем на страницу входа
      router.replace("/");
      return;
    }
    
    // Токен есть
    getMe()
      .then(setUser)
      .catch(() => {
        // Токен невалиден или истёк
        clearStoredToken();
        router.replace("/");
      })
      .finally(() => setReady(true));
  }, [isLoginPage, router]);

  // Проверяем генерацию мнемокарточки
  useEffect(() => {
    function onStart() {
      // Увеличиваем счётчик активных генераций
      activeGenerationsRef.current += 1;
      // Включаем индикатор загрузки
      setGlobalMnemoGenerating(true);
      // Скрываем предыдущее уведомление
      setGlobalMnemoReadyToast(false);
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current);
        toastTimerRef.current = null;
      }
    }

    // Несколько карточек могут генерироваться одновременно
    function onEnd() {
      activeGenerationsRef.current = Math.max(0, activeGenerationsRef.current - 1);
      if (activeGenerationsRef.current > 0) return;
      setGlobalMnemoGenerating(false);
    }

    // Успешный ответ сервера
    function onSuccess() {
      setGlobalMnemoReadyToast(true);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setGlobalMnemoReadyToast(false), 5000);
    }

    // Подписываемся на события
    window.addEventListener(MNEMO_GENERATION_START_EVENT, onStart as EventListener);
    window.addEventListener(MNEMO_GENERATION_END_EVENT, onEnd as EventListener);
    window.addEventListener(MNEMO_GENERATION_SUCCESS_EVENT, onSuccess as EventListener);

    // При размонтировании компонента отписываемся
    return () => {
      window.removeEventListener(MNEMO_GENERATION_START_EVENT, onStart as EventListener);
      window.removeEventListener(MNEMO_GENERATION_END_EVENT, onEnd as EventListener);
      window.removeEventListener(MNEMO_GENERATION_SUCCESS_EVENT, onSuccess as EventListener);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  // Страница входа
  if (isLoginPage) {
    return <>{children}</>;
  }

  // Если приложение еще не готово, то показываем загрузку
  if (!ready || !user) {
    return (
      <main className="app-screen">
        <div className="glass glass-loading">
          <div className="loading-dots" aria-hidden>
            <span />
            <span />
            <span />
          </div>
          <p className="app-muted" style={{ marginTop: 16 }}>Загрузка...</p>
        </div>
      </main>
    );
  }

  return (
    <AvatarProvider initialAvatarUrl={user.avatar_url ?? null}>
      <AppShell user={user} onLogout={() => { clearStoredToken(); router.replace("/"); }}>
        {globalMnemoGenerating && (
          <div className="mnemo-generation-indicator" role="status" aria-live="polite">
            <span className="mnemo-generation-spinner" aria-hidden />
            <span>Подождите, идет генерация карточки...</span>
          </div>
        )}
        {globalMnemoReadyToast && (
          <div className="mnemo-ready-toast" role="status" aria-live="polite">
            Генерация закончилась, можно начать обучение
          </div>
        )}
        {children}
      </AppShell>
    </AvatarProvider>
  );
}
