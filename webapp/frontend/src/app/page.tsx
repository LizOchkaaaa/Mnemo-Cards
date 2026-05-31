// Файл главной страницы

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import AuthForm from "../components/AuthForm";
import { clearStoredToken, getMe, getStoredToken, type UserInfo } from "../lib/api";

// Главный компонент страницы
export default function HomePage() {
  const router = useRouter();
  // Проверка аутентификации
  const [authReady, setAuthReady] = useState(false);
  // Данные пользователя
  const [user, setUser] = useState<UserInfo | null>(null);

  // Проверка авторизации
  useEffect(() => {
    // Проверяем токен
    const token = getStoredToken();
    if (!token) {
      setAuthReady(true);
      return;
    }
    // Если токен рабочий, то пользователь залогинен
    getMe()
      .then((u) => {
        setUser(u);
        router.replace("/settings");
      })
      .catch(() => {
        clearStoredToken();
        setUser(null);
      })
      .finally(() => setAuthReady(true));
  }, [router]);

  // После успешного входа получаем данные
  async function handleAuthSuccess() {
    const u = await getMe();
    setUser(u);
    router.replace("/settings");
  }

  if (!authReady) {
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

  // Если пользователь уже залогинен, то не показываем страницу входа
  if (user) {
    return null;
  }

  // Если не залогинен, то показываем форму входа
  return (
    <main className="auth-screen">
      <div className="auth-header">
        <h1>MnemoCards</h1>
        <p>Войдите или зарегистрируйтесь, чтобы начать обучаться</p>
      </div>
      <AuthForm onSuccess={handleAuthSuccess} />
    </main>
  );
}
