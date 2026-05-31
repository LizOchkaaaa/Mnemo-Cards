# Файл с операциями пользователей в PostgreSQL

from __future__ import annotations

import secrets
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import User
from app.auth.password_utils import hash_password, verify_password

# Операции пользователями
class AuthStorePostgres:
    # Инициализация
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    # Инициализируем новую сессию
    def _session(self) -> Session:
        return self._session_factory()

    # Возвращаем словарь пользователя по email
    def get_user(self, email: str) -> dict | None:
        key = email.strip().lower()
        if not key:
            return None

        # Открываем сессию
        with self._session() as session:
            # Ищем единственную запись пользователя по email
            user = session.execute(select(User).where(User.email == key)).scalar_one_or_none()
            if not user:
                return None

            # Возвращаем только нужные поля
            return {
                "email": user.email, 
                "username": user.username, 
                "password_hash": user.password_hash,
                "avatar_url": getattr(user, "avatar_url", None),
            }

    # Возвращаем ID пользователя по email
    def get_user_id(self, email: str) -> int | None:
        key = email.strip().lower()
        if not key:
            return None

        # Открываем сессию
        with self._session() as session:
            # Забираем только колонку User.id.
            row = session.execute(select(User.id).where(User.email == key)).scalar_one_or_none()
            return row

    # Возвращаем базовые данные пользователя по его ID
    def get_user_by_id(self, user_id: int) -> dict | None:
        # Открываем сессию
        with self._session() as session:
            user = session.get(User, user_id)
            if not user:
                return None

            return {
                "email": user.email,
                "username": user.username,
                "avatar_url": getattr(user, "avatar_url", None),
            }

    # Возвращаем дату регистрации
    def get_user_created_at(self, user_id: int) -> datetime | None:
        # Открываем сессию
        with self._session() as session:
            # Читаем только created_at по user_id
            val = session.execute(
                select(User.created_at).where(User.id == user_id)
            ).scalar_one_or_none()
            return val if val else None

    # Создаем нового пользователя
    def create_user(self, email: str, password: str, username: str | None = None) -> dict:
        key = email.strip().lower()
        if not key:
            raise ValueError("Email is required")

        with self._session() as session:
            # Проверяем, не занят ли email
            if session.execute(select(User).where(User.email == key)).scalar_one_or_none():
                raise ValueError("User with this email already exists")

            # Нормализуем
            username = (username or "").strip() or None
            # Собираем ORM-объект пользователя
            user = User(
                email=key,
                username=username,
                password_hash=hash_password(password),
            )

            # Добавляем объект в текущую сессию
            session.add(user)
            session.commit()
            # Обновляем объект
            session.refresh(user)

            # Возвращаем данные
            return {
                "email": user.email,
                "username": user.username, 
                "avatar_url": getattr(user, "avatar_url", None),
            }

    # Обновляем avatar_url
    def update_avatar(self, user_id: int, avatar_url: str | None) -> bool:
        # Открываем сессию
        with self._session() as session:
            user = session.get(User, user_id)
            if not user:
                return False

            # Сохраняем URL аватара
            user.avatar_url = (avatar_url or "").strip() or None
            # Сбрасываем бинарные данные
            user.avatar_data = None
            user.avatar_content_type = None
            user.avatar_public_token = None
            # Фиксируем изменения
            session.commit()
            return True

    # Сохраняем загруженный файл аватара
    def update_avatar_from_upload(
        self,
        user_id: int,
        data: bytes,
        content_type: str,
        api_prefix: str,
    ) -> bool:
        # Генерируем случайный токен
        token = secrets.token_hex(32)
        # Формируем публичный URL
        public_url = f"{api_prefix}/auth/avatar/public/{token}"

        # Открываем сессию
        with self._session() as session:
            # Ищем пользователя
            user = session.get(User, user_id)
            if not user:
                return False

            # Сохраняем бинарные данные
            user.avatar_data = data
            # Нормализуем content-type
            user.avatar_content_type = (content_type or "image/jpeg").split(";")[0].strip()[:64]
            # Сохраняем публичный токен
            user.avatar_public_token = token
            # Обновляем URL аватара на публичный endpoint
            user.avatar_url = public_url
            session.commit()
            return True

    # Возвращаем бинарный аватар и MIME по публичному токену
    def get_avatar_blob_by_public_token(self, token: str) -> tuple[bytes, str] | None:
        # Чистим входной токен
        t = (token or "").strip()
        if not t or len(t) > 128:
            return None

        # Открываем сессию
        with self._session() as session:
            # Ищем пользователя по токену бинарного аватара
            user = session.scalar(select(User).where(User.avatar_public_token == t))
            if not user or not user.avatar_data:
                return None

            # Выбираем MIME с дефолтом image/jpeg
            mime = (user.avatar_content_type or "image/jpeg").strip()
            return (user.avatar_data, mime)

    # Обновляем отображаемое имя пользователя
    def update_username(self, user_id: int, username: str | None) -> bool:
        # Открываем сессию
        with self._session() as session:
            # Ищем пользователя
            user = session.get(User, user_id)
            if not user:
                return False

            # Нормализуем
            user.username = (username or "").strip() or None
            session.commit()
            return True

    # Обновляем email
    def update_email(self, user_id: int, new_email: str, password: str) -> bool:
        # Нормализуем новый email
        new_key = new_email.strip().lower()
        if not new_key:
            return False

        # Открываем сессию
        with self._session() as session:
            # Ищем пользователя, который меняет email
            user = session.get(User, user_id)
            if not user:
                return False

            # Проверяем, что введен корректный текущий пароль
            if not verify_password(password, user.password_hash):
                return False

            # Проверяем, что новый email не занят любой записью в users
            if session.execute(select(User).where(User.email == new_key)).scalar_one_or_none():
                return False

            # Применяем новый email
            user.email = new_key
            session.commit()
            return True

    # Проверяем логин
    def verify_user(self, email: str, password: str) -> dict | None:
        # Получаем пользователя по email
        user = self.get_user(email)
        if not user:
            return None

        # Сверяем пароль с bcrypt-хешем из базы данных
        if not verify_password(password, user["password_hash"]):
            return None

        # Возвращаем данные
        return {
            "email": user["email"], 
            "username": user.get("username"), 
            "avatar_url": user.get("avatar_url"),
        }