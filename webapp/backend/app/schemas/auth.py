# Схемы для авторизации, где определяются структуры данных

from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field

# Схема для регистрации нового пользователя
class RegisterRequest(BaseModel):
    # Игнорируем лишние поля в запросе
    model_config = ConfigDict(extra="ignore")
    # Email пользователя
    email: str = Field(..., min_length=1, max_length=256)
    # Пароль
    password: str = Field(..., min_length=6, max_length=128)
    # Имя пользователя
    username: str | None = Field(None, max_length=64)

# Схема для входа пользователя
class LoginRequest(BaseModel):
    # Игнорируем лишние поля в запросе
    model_config = ConfigDict(extra="ignore")
    # Email пользователя
    email: str = Field(..., min_length=1, max_length=256)
    # Пароль
    password: str = Field(..., min_length=1, max_length=128)

# Схема с информацией о пользователе
class UserInfo(BaseModel):
    # Email пользователя
    email: str
    # Имя пользователя
    username: str | None
    # URL аватара
    avatar_url: str | None = None

# Схема для обновления профиля пользователя
class UpdateProfileRequest(BaseModel):
    # Игнорируем лишние поля в запросе
    model_config = ConfigDict(extra="ignore")
    # Новое имя пользователя
    username: str | None = Field(None, max_length=64)
    # Новый email
    email: str | None = Field(None, max_length=256)
    # Пароль для подтверждения при смене email
    password: str | None = Field(None, min_length=6, max_length=128)
    # Новый URL аватара
    avatar_url: str | None = Field(None, max_length=512)

# Схема ответа при успешной регистрации или входе
class AuthResponse(BaseModel):
    # JWT токен
    access_token: str
    # Тип токена
    token_type: str = "bearer"
    # Информация о пользователе
    user: UserInfo 