// Файл формы входа и регистрации

"use client";

import { FormEvent, useState } from "react";
import { login, register, setStoredToken } from "../lib/api";

// Режим: вход или регистрация
type Mode = "login" | "register";

type AuthFormProps = {
  onSuccess: () => void;
};

// Иконка конверта
const IconMail = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <rect x="2" y="4" width="20" height="16" rx="2" />
    <path d="m22 6-10 7L2 6" />
  </svg>
);

// Иконка замка
const IconLock = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </svg>
);

// Иконка пользователя
const IconUser = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

// Компонент формы регистрации/авторизации
export default function AuthForm({ onSuccess }: AuthFormProps) {
  const [mode, setMode] = useState<Mode>("login");           // Текущий режим
  const [email, setEmail] = useState("");                    // Email
  const [password, setPassword] = useState("");              // Пароль
  const [username, setUsername] = useState("");              // Имя пользователя
  const [loading, setLoading] = useState(false);             // Флаг загрузки
  const [error, setError] = useState<string | null>(null);   // Сообщение об ошибке
  const [info, setInfo] = useState<string | null>(null);     // Информационное сообщение

  // Обрабатка отправки формы
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Сбрасываем предыдущие сообщения перед новым запросом
    setError(null);
    setInfo(null);
    setLoading(true);
    
    try {
      if (mode === "register") {
        // Отправляем запрос на регистрацию
        await register(email.trim(), password, username.trim() || undefined);
        // После успешной регистрации:
        setMode("login");
        setPassword("");
        setInfo("Регистрация прошла успешно. Теперь войдите в аккаунт");
      } 
      else {
        // Отправляем запрос на вход, получаем токен
        const res = await login(email.trim(), password);
        // Сохраняем JWT токен в localStorage
        setStoredToken(res.access_token);
        onSuccess();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      // Индикатор загрузки
      setLoading(false);
    }
  }

  return (
    <div className="auth-glass">
      <h2 className="auth-title">{mode === "login" ? "ВХОД" : "РЕГИСТРАЦИЯ"}</h2>
      <form className="grid" onSubmit={handleSubmit} style={{ gap: 0 }}>
        <label style={{ marginBottom: 20 }}>
          <span className="visually-hidden">Email</span>
          <span className="auth-input-wrap">
            <IconMail />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="hello@example.com"
              required
              autoComplete="email"
            />
          </span>
        </label>

        {mode === "register" && (
          <label style={{ marginBottom: 20 }}>
            <span className="visually-hidden">Имя</span>
            <span className="auth-input-wrap">
              <IconUser />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Ваше имя"
                autoComplete="username"
              />
            </span>
          </label>
        )}

        <label style={{ marginBottom: 20 }}>
          <span className="visually-hidden">Пароль</span>
          <span className="auth-input-wrap">
            <IconLock />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={mode === "register" ? "не менее 6 символов" : "••••••••"}
              required
              minLength={mode === "register" ? 6 : 1}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </span>
        </label>

        {error && <p className="auth-error">{error}</p>}
        {!error && info && <p className="muted" style={{ marginBottom: 8 }}>{info}</p>}

        <button 
          type="submit" 
          className="auth-btn-gradient" 
          disabled={loading}
        >
          {loading ? (
            <span className="loading-dots" aria-hidden>
              <span />
              <span />
              <span />
            </span>
          ) : mode === "login" ? (
            "Войти"
          ) : (
            "Зарегистрироваться"
          )}
        </button>
      </form>

      <p className="auth-switch">
        {mode === "login" ? (
          <>
            Нет аккаунта?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("register");   // Переключаем режим
                setError(null);        // Очищаем ошибки
                setInfo(null);         // Очищаем информационные сообщения
              }}
            >
              Регистрация
            </button>
          </>
        ) : (
          <>
            Уже есть аккаунт?{" "}
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
                setInfo(null);
              }}
            >
              Вход
            </button>
          </>
        )}
      </p>
    </div>
  );
}