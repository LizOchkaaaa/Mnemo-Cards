// Файл страницы настроек

"use client";

import { useEffect, useRef, useState } from "react";
import { useAvatar } from "@/contexts/AvatarContext";
import { getMe, updateProfile, uploadAvatarPhoto, type UserInfo } from "@/lib/api";
import VerseGeneratorSelect from "@/components/VerseGeneratorSelect";
import VersePromptEditor from "@/components/VersePromptEditor";
import ImageGeneratorSelect from "@/components/ImageGeneratorSelect";

// Пресеты из файла
const PROFILE_PHOTO_SOURCES = [1, 2, 3, 4, 5].map((n) => `/avatars/example-${n}.jpg`);

// Получение первой буквы имени или email для отображения
function getInitial(name: string | null, email: string): string {
  if (name?.trim()) return name.trim().charAt(0).toUpperCase();
  if (email?.trim()) return email.trim().charAt(0).toUpperCase();
  return "?";
}

// Страница настроек пользователя
export default function SettingsPage() {
  // Данные текущего пользователя
  const [user, setUser] = useState<UserInfo | null>(null);
  const { avatarUrl, setAvatarUrl } = useAvatar();
  const [editingUsername, setEditingUsername] = useState(false);
  const [usernameDraft, setUsernameDraft] = useState("");
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [emailDraft, setEmailDraft] = useState("");
  const [passwordForEmail, setPasswordForEmail] = useState("");
  const [profileError, setProfileError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [mainAvatarImgBroken, setMainAvatarImgBroken] = useState(false);
  const [brokenPresetThumbs, setBrokenPresetThumbs] = useState<Record<number, true>>({});

  useEffect(() => {
    getMe()
      .then((u) => {
        setUser(u);
        setAvatarUrl(u.avatar_url ?? null);
      })
      .catch(() => setUser(null));
  }, [setAvatarUrl]);

  useEffect(() => {
    setMainAvatarImgBroken(false);
    setBrokenPresetThumbs({});
  }, [user?.avatar_url, avatarUrl]);

  // Выбор аватара из предустановленных
  async function handleSelectPhoto(index: number) {
    const url = PROFILE_PHOTO_SOURCES[index];
    setAvatarUrl(url);
    try {
      const updated = await updateProfile({ avatar_url: url });
      setUser(updated);
      setAvatarUrl(updated.avatar_url ?? url);
      setProfileError(null);
    } catch (e) {
      setProfileError(e instanceof Error ? e.message : "Не удалось сохранить фото");
    }
  }

  // Загрузка своего аватара
  function handleAddPhoto() {
    setProfileError(null);
    fileInputRef.current?.click();
  }

  // Редактирование имени
  function handleEditUsername() {
    setUsernameDraft(user?.username?.trim() ?? "");
    setEditingUsername(true);
    setProfileError(null);
  }

  // Сохранение нового имени
  async function saveUsername() {
    if (!editingUsername) return;
    setEditingUsername(false);
    const value = usernameDraft.trim() || null;
    // Если имя не изменилось, то не отправляем запрос
    if (value === (user?.username?.trim() || null)) return;
    try {
      const updated = await updateProfile({ username: value });
      setUser(updated);
      setProfileError(null);
    } catch (e) {
      setProfileError(e instanceof Error ? e.message : "Не удалось сохранить имя");
    }
  }

  // Редактирование email
  function handleEditEmail() {
    setEmailDraft(user?.email ?? "");
    setPasswordForEmail("");
    setEmailModalOpen(true);
    setProfileError(null);
  }

  // Сохранение нового email
  async function saveEmail() {
    if (!passwordForEmail.trim()) {
      setProfileError("Введите пароль для подтверждения");
      return;
    }
    try {
      const updated = await updateProfile({
        email: emailDraft.trim(),
        password: passwordForEmail,
      });
      setUser(updated);
      setEmailModalOpen(false);
      setProfileError(null);
    } catch (e) {
      setProfileError(e instanceof Error ? e.message : "Не удалось сменить почту");
    }
  }

  // Обработка загруженного пользователем файла аватара
  async function onAvatarFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    
    if (!file) return;
    
    // Валидация типа файла
    if (!file.type.startsWith("image/")) {
      setProfileError("Выберите файл изображения (JPEG, PNG, GIF или WebP)");
      return;
    }
    
    // Валидация размера (не более 5 МБ)
    if (file.size > 5 * 1024 * 1024) {
      setProfileError("Размер файла не более 5 МБ");
      return;
    }
    
    try {
      const updated = await uploadAvatarPhoto(file);
      setUser(updated);                   
      if (updated.avatar_url) setAvatarUrl(updated.avatar_url);
      setProfileError(null);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Не удалось загрузить фото");
    }
  }

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        onChange={onAvatarFileChange}
        style={{ display: "none" }}
        aria-hidden
      />
      {emailModalOpen && (
        <div className="settings-modal-backdrop" onClick={() => { setEmailModalOpen(false); setProfileError(null); }}>
          <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="app-section-title">Смена электронной почты</h3>
            <p className="app-muted" style={{ marginBottom: 12 }}>
              Введите новый адрес почты и текущий пароль для подтверждения
            </p>
            <label className="settings-modal-label">
              Новая почта
              <input
                type="email"
                value={emailDraft}
                onChange={(e) => setEmailDraft(e.target.value)}
                className="settings-modal-input"
                placeholder="email@example.com"
              />
            </label>
            <label className="settings-modal-label">
              Текущий пароль
              <input
                type="password"
                value={passwordForEmail}
                onChange={(e) => setPasswordForEmail(e.target.value)}
                className="settings-modal-input"
                placeholder="••••••••"
              />
            </label>
            {profileError && <p className="app-error" style={{ marginBottom: 8 }}>{profileError}</p>}
            <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
              <button type="button" className="app-btn-gradient" onClick={saveEmail}>
                Сохранить
              </button>
              <button type="button" className="app-btn-outline" onClick={() => { setEmailModalOpen(false); setProfileError(null); }}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
      <section className="glass glass-form" style={{ maxWidth: 720 }}>
        <h2 className="app-title">Личная информация</h2>
        {profileError && !emailModalOpen && (
          <p className="app-error" style={{ marginBottom: 16 }}>{profileError}</p>
        )}
        <div className="settings-personal">
          <div className="settings-personal-photo">
            <p className="app-section-title">Фотография профиля</p>
            <div className="settings-avatar-row">
              <div className="settings-avatar-main" aria-hidden>
                {selectedIndex !== null && !mainAvatarImgBroken ? (
                  <img
                    src={PROFILE_PHOTO_SOURCES[selectedIndex]}
                    alt=""
                    width={100}
                    height={100}
                    className="settings-avatar-img"
                    draggable={false}
                    onError={() => setMainAvatarImgBroken(true)}
                  />
                ) : avatarUrl && !isPresetAvatarUrl(avatarUrl) && !mainAvatarImgBroken ? (
                  <img
                    src={avatarUrl}
                    alt=""
                    width={100}
                    height={100}
                    className="settings-avatar-img"
                    draggable={false}
                    onError={() => setMainAvatarImgBroken(true)}
                  />
                ) : user ? (
                  <span className="settings-avatar-initial" aria-hidden>
                    {getInitial(user.username, user.email)}
                  </span>
                ) : (
                  <span className="app-muted">—</span>
                )}
              </div>
              <div className="settings-avatar-options">
                {PROFILE_PHOTO_SOURCES.map((src, i) => (
                  <button
                    key={i}
                    type="button"
                    className={`settings-avatar-option ${selectedIndex === i ? "settings-avatar-option-selected" : ""}`}
                    aria-label={`Выбрать фото ${i + 1}`}
                    onClick={() => handleSelectPhoto(i)}
                  >
                    {brokenPresetThumbs[i] ? (
                      <span className="settings-avatar-thumb-fallback">{i + 1}</span>
                    ) : (
                      <img
                        src={src}
                        alt=""
                        width={52}
                        height={52}
                        className="settings-avatar-option-img"
                        draggable={false}
                        onError={() =>
                          setBrokenPresetThumbs((prev) => ({ ...prev, [i]: true }))
                        }
                      />
                    )}
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="settings-avatar-add"
                onClick={handleAddPhoto}
                aria-label="Добавить фото"
                title="Добавить фото"
              >
                +
              </button>
            </div>
          </div>

          <div className="settings-divider" />

          <div className="settings-field">
            <div className="settings-field-head">
              <p className="app-section-title">Имя пользователя</p>
              {!editingUsername && (
                <button
                  type="button"
                  className="settings-edit-link"
                  onClick={handleEditUsername}
                >
                  Редактировать
                </button>
              )}
            </div>
            {editingUsername ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <input
                  type="text"
                  value={usernameDraft}
                  onChange={(e) => setUsernameDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveUsername()}
                  className="settings-modal-input"
                  style={{ flex: "1", minWidth: 160 }}
                  placeholder="Имя"
                  autoFocus
                />
                <button type="button" className="app-btn-gradient" onClick={saveUsername}>
                  Сохранить
                </button>
                <button type="button" className="app-btn-outline" onClick={() => { setEditingUsername(false); setProfileError(null); }}>
                  Отмена
                </button>
              </div>
            ) : (
              <p className="settings-field-value">
                {user?.username?.trim() || user?.email || "—"}
              </p>
            )}
          </div>

          <div className="settings-divider" />

          <div className="settings-field">
            <div className="settings-field-head">
              <p className="app-section-title">Электронная почта</p>
              <button
                type="button"
                className="settings-edit-link"
                onClick={handleEditEmail}
              >
                Редактировать
              </button>
            </div>
            <p className="settings-field-value">{user?.email || "—"}</p>
          </div>
        </div>
      </section>

      <section className="glass glass-result">
        <h2 className="app-title">Настройки обучения</h2>
        <div style={{ marginTop: 24 }}>
          <VerseGeneratorSelect label="Генератор стихотворений" />
          <ImageGeneratorSelect label="Генератор изображений" />
          <VersePromptEditor />
        </div>
      </section>

      <section className="glass glass-result">
        <h2 className="app-title">Настройки интерфейса</h2>
        <div style={{ marginTop: 24 }}>
          <p className="app-section-title">Язык</p>
          <p className="settings-field-value" style={{ marginTop: 8 }}>
            Русский язык
          </p>
        </div>
      </section>
    </>
  );
}
