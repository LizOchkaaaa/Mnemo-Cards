// Файл для подключение шрифта Figtree и глобальных стилей, метаданные и страницы

import type { Metadata } from "next";
import { Figtree } from "next/font/google";
import "./globals.css";
import AppLayoutWrapper from "@/components/AppLayoutWrapper";

// Шрифт Figtree
const figtree = Figtree({
  subsets: ["latin", "latin-ext"],
  display: "swap",
  variable: "--font-sans"
});

// Метаданные
export const metadata: Metadata = {
  title: "MnemoCards — Изучай языки легко",
  description: "Использование больших моделей для генерации мнемокарточек для запоминания слов"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" className={figtree.variable}>
      <body>
        <AppLayoutWrapper>{children}</AppLayoutWrapper>
      </body>
    </html>
  );
}
