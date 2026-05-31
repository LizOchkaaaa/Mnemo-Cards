// Файл страницы прогресса

"use client";

import { useEffect, useState } from "react";
import { getLearningStats, type LearningStats } from "@/lib/api";

// Склонение слова "день" в зависимости от числа
function pluralDays(n: number): string {
  if (n === 1) return "день";
  if (n >= 2 && n <= 4) return "дня";
  return "дней";
}

// Склонение слова "слово" в зависимости от числа
function pluralWords(n: number): string {
  if (n === 1) return "слово";
  if (n >= 2 && n <= 4) return "слова";
  return "слов";
}

// Загрузка статистики обучения
function loadStats() {
  return getLearningStats()
    .then((s) => ({ stats: s, error: null }))
    .catch((e) => ({ stats: null, error: e instanceof Error ? e.message : "Ошибка загрузки" }));
}

// Страница прогресса обучения
export default function ProgressPage() {
  const [stats, setStats] = useState<LearningStats | null>(null);    // Данные статистики
  const [loading, setLoading] = useState(true);                      // Флаг загрузки
  const [error, setError] = useState<string | null>(null);           // Ошибка при загрузке

  // Загрузка статистики при открытии страницы
  useEffect(() => {
    let cancelled = false;
    loadStats().then(({ stats: s, error: e }) => {
      if (!cancelled) {
        setStats(s);
        setError(e);
      }
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    
    // Если страница закрылась, отменяем обновление состояния
    return () => { cancelled = true; };
  }, []);

  // Обновление статистики при возврате на страницу
  useEffect(() => {
    const onRefresh = () => {
      // Обновляем только когда страница видима
      if (document.visibilityState === "visible") {
        loadStats().then(({ stats: s, error: e }) => {
          setStats(s);
          if (e) setError(e);
        });
      }
    };
    document.addEventListener("visibilitychange", onRefresh);
    return () => document.removeEventListener("visibilitychange", onRefresh);
  }, []);

  if (loading) {
    return (
      <section className="glass glass-result">
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: 24 }}>
          <div className="loading-dots" aria-hidden>
            <span />
            <span />
            <span />
          </div>
          <span className="app-muted">Загрузка прогресса...</span>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="glass glass-result">
        <p className="app-error" style={{ padding: 24 }}>{error}</p>
      </section>
    );
  }

  // Если статистики нет, то подставляем нули
  const s = stats ?? { days_learning: 0, words_total: 0, words_learned: 0 };
  const wordsLearned = s.words_learned ?? 0;
  const wordsToLearn = Math.max(0, s.words_total - wordsLearned);

  return (
    <section className="glass glass-result progress-section">
      <h2 className="app-title">Мой прогресс</h2>
      <p className="app-muted" style={{ marginTop: 4, marginBottom: 24 }}>
        Статистика обучения
      </p>

      <div className="progress-cards">
        <div className="progress-card progress-card-days">
          <div className="progress-card-icon">📅</div>
          <div className="progress-card-value">{s.days_learning}</div>
          <div className="progress-card-label">{pluralDays(s.days_learning)} занимаюсь</div>
        </div>

        <div className="progress-card progress-card-learned">
          <div className="progress-card-icon">✅</div>
          <div className="progress-card-value">{wordsLearned}</div>
          <div className="progress-card-label">{pluralWords(wordsLearned)} выучено</div>
        </div>

        <div className="progress-card progress-card-remaining">
          <div className="progress-card-icon">🎯</div>
          <div className="progress-card-value">{wordsToLearn}</div>
          <div className="progress-card-label">{pluralWords(wordsToLearn)} осталось</div>
        </div>
      </div>
    </section>
  );
}
