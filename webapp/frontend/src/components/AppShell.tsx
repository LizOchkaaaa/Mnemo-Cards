// Файл шапки с навигацией для страниц «Обучение», «Прогресс», «Словарь», «Настройки»

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAvatar } from "../contexts/AvatarContext";
import { useMnemoGenerationPending, type UserInfo } from "@/lib/api";

type AppShellProps = {
  user: UserInfo;          
  onLogout: () => void;
  children: React.ReactNode;
};

// Компонент логотипа
function LogoImage() {
  return (
    <img
      src="/logo.png"
      alt="MnemoCards"
      width={200}
      height={85}
      className="app-header-logo"
    />
  );
}

// Компонент обертки приложения
export default function AppShell({ user, onLogout, children }: AppShellProps) {
  // Получаем текущий путь URL
  const pathname = usePathname();
  // Получаем URL аватара
  const { avatarUrl } = useAvatar();
  // Отслеживаем, идёт ли сейчас генерация мнемоники
  const mnemoGenerating = useMnemoGenerationPending();
  // Список навигации
  const navItems = [
    { href: "/progress", label: "Прогресс" },
    { href: "/learning", label: "Обучение" },
    { href: "/dictionary", label: "Мой словарь" },
    { href: "/settings", label: "Настройки" },
  ];

  // Проверяем, находимся ли мы на странице прогресса
  const isProgressPage = pathname === "/progress";

  return (
    <main className={`app-screen ${isProgressPage ? "app-screen--progress" : ""}`}>
      <header className="app-header">
        {mnemoGenerating ? (
          <span
            className="app-header-brand app-header-brand--disabled"
            title="Дождитесь окончания генерации карточки"
            aria-disabled
          >
            <LogoImage />
          </span>
        ) : (
          <Link href="/learning" className="app-header-brand">
            <LogoImage />
          </Link>
        )}

        <nav className="app-header-nav-pill">
          {navItems.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`app-header-nav-link ${pathname === href ? "app-header-nav-link-active" : ""}`}
              title={
                mnemoGenerating && href === "/learning" ? "При генерации карточки обучение недоступно" : undefined
              }
            >
              {label}
            </Link>
          ))}
        </nav>
        
        <div className="app-header-right">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt="Аватар пользователя"
              width={40}
              height={40}
              className="app-header-avatar"
            />
          ) : null}

          <span className="app-header-user">{user.username || user.email}</span>

          <button
            type="button"
            className="app-header-logout"
            onClick={onLogout}
          >
            Выйти
          </button>
        </div>
      </header>
      {children}
    </main>
  );
}