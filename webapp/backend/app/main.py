# Главный файл FastAPI приложения, который запускает весь сервер

from __future__ import annotations
import logging
import json
import urllib.error
import urllib.parse
import urllib.request
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, File, FastAPI, Header, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import AuthStorePostgres, create_token, decode_token
from app.auth.password_utils import truncate_password_for_bcrypt
from app.core import Settings, get_engine, get_session_factory, init_db
from app.repository.decomposition_cache_repository import DecompositionCacheRepository
from app.repository.mnemo_cache_repository import WordMnemoRepository
from app.repository.user_words_repository import UserWordsRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UpdateProfileRequest, UserInfo
from app.mnemo import decompose as decompose_word, get_ipa, init_decomposer
from app.core.database import UserWord
from app.schemas.dictionary import (
    DecompositionResponse,
    ExportDocxRequest,
    PronunciationResponse,
    SrsReviewRequest,
    TranscriptionResponse,
    TranslationResponse,
    UserWordCreate,
    UserWordResponse,
    UserWordUpdate,
)
from app.schemas.mnemo import GenerateMnemoRequest, HealthResponse, MnemoResponse
from app.services.dictionary_translate import fetch_mymemory_translation
from app.services.ipa_word import normalize_ipa_lang_code
from app.services.pronunciation_espeak import synthesize_word_wav_espeak
from app.services.mnemo_service import MnemoService
from app.services.cards_export_docx import build_user_cards_docx

# Загружаем настройки из переменных окружения
settings = Settings()
logger = logging.getLogger(__name__)

# Настройка логгера
_app_pkg_logger = logging.getLogger("app")
_app_pkg_logger.setLevel(logging.INFO)
_app_pkg_logger.propagate = False

if not _app_pkg_logger.handlers:
    _app_log_handler = logging.StreamHandler()
    _app_log_handler.setLevel(logging.INFO)
    _app_log_handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    _app_pkg_logger.addHandler(_app_log_handler)

# Инициализируем декомпозитор слов
init_decomposer(settings.decomposer_model_dir)

# Разрешённые MIME типы для аватаров
ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Создаём движок для подключения к PostgreSQL
_engine = get_engine(settings.database_url)
init_db(_engine)
_session_factory = get_session_factory(_engine)

# Репозитории для работы с таблицами
auth_store = AuthStorePostgres(_session_factory)
user_words_repo = UserWordsRepository(_session_factory)
mnemo_cache_repo = WordMnemoRepository(_session_factory, user_words_repo)
decomposition_cache_repo = DecompositionCacheRepository(_session_factory)

# Сервис мнемоники
service = MnemoService(
    settings,
    mnemo_cache_repo=mnemo_cache_repo,
    decomposition_cache_repo=decomposition_cache_repo,
    user_words_repo=user_words_repo,
)

# Создаём приложение FastAPI
app = FastAPI(title=settings.app_name)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins_tuple()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создаём папки для хранения файлов
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.generated_images_dir.mkdir(parents=True, exist_ok=True)

# Делаем папки доступными по URL
app.mount("/static/mnemo", StaticFiles(directory=str(settings.cache_dir)), name="mnemo-cache")
app.mount("/static/generated", StaticFiles(directory=str(settings.generated_images_dir)), name="generated-images")

# Захардкоженные картинки мнемоник
_preset_assets_dir = Path(__file__).resolve().parent / "preset_assets"
if _preset_assets_dir.is_dir():
    app.mount(
        f"{settings.api_prefix}/mnemo/preset-assets",
        StaticFiles(directory=str(_preset_assets_dir)),
        name="mnemo-preset-assets",
    )


# Получение сервиса мнемоники
def get_service() -> MnemoService:
    return service

# Преобразуем ORM-объект
def _user_word_response_from_orm(
    e: UserWord, 
    *,                        
    parts: list[str] | None = None, 
) -> UserWordResponse:
    # Получаем SM-2
    sr = getattr(e, "srs_state", None)
    
    # Формируем и возвращаем объект ответа
    return UserWordResponse(
        id=e.id,                                                  # ID
        word=e.word,                                              # Слово
        translation=e.translation,                                # Перевод
        transcription=getattr(e, "transcription", None),          # IPA транскрипция
        category=getattr(e, "category", None),                    # Категория слова
        word_language=getattr(e, "word_language", None) or "en",  # Язык слова
        is_favorite=e.is_favorite,                                # Флаг "избранное"
        is_learned=getattr(e, "is_learned", False),               # Флаг "выучено"
        parts=parts,                                              # Список частей слова

        srs_easiness=getattr(sr, "srs_easiness", None) if sr else None,             # Коэффициент лёгкости
        srs_interval_days=getattr(sr, "srs_interval_days", None) if sr else None,   # Интервал до следующего повторения (дней)
        srs_repetitions=getattr(sr, "srs_repetitions", None) if sr else None,       # Количество повторений
        srs_next_review_at=getattr(sr, "srs_next_review_at", None) if sr else None, # Дата следующего повторения
    )

# ID пользователя
def get_current_user_id(authorization: str | None = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    # Извлекаем сам токен
    token = authorization[7:].strip()
    # Декодируем и верифицируем JWT токен
    payload = decode_token(token, settings.jwt_secret, settings.jwt_algorithm)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # Извлекаем email из payload и нормализуем
    email = str(payload["sub"]).strip().lower()
    # Получаем user_id по email из базы данных
    user_id = auth_store.get_user_id(email)
    if user_id is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user_id

# ID пользователя необязательное
def get_optional_user_id(authorization: str | None = Header(None)) -> int | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    # Извлекаем токен
    token = authorization[7:].strip()
    if not token:
        return None
    # Декодируем токен
    payload = decode_token(token, settings.jwt_secret, settings.jwt_algorithm)
    if not payload or "sub" not in payload:
        return None
    # Извлекаем email и получаем user_id
    email = str(payload["sub"]).strip().lower()
    return auth_store.get_user_id(email)

# Получение аудио из Free Dictionary API
def _fetch_pronunciation_audio_url(word: str) -> str | None:
    # Нормализуем слово
    w = (word or "").strip().lower()
    if not w:
        return None
    # Формируем URL для API запроса
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(w)}"
    try:
        # Создаём запрос
        req = urllib.request.Request(url, headers={"User-Agent": "MnemoBackend/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
            
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
    # Проверяем, что API вернул список
    if not isinstance(data, list):
        return None

    for entry in data:
        if not isinstance(entry, dict):
            continue
        
        # Проходим по всем фонетическим вариантам слова
        for p in entry.get("phonetics") or []:
            if isinstance(p, dict) and p.get("audio"):
                # Возвращаем URL
                return str(p["audio"]).strip()
            
    return None

# Эндпоинты

# Генерация мнемокарточки
@app.post(f"{settings.api_prefix}/mnemo/generate", response_model=MnemoResponse)
def generate_mnemo(
    request: GenerateMnemoRequest,
    user_id: int = Depends(get_current_user_id),
    mnemo_service: MnemoService = Depends(get_service),
) -> MnemoResponse:
    logger.info(
        "[MNEMO] HTTP POST /mnemo/generate word=%r verse_generator=%s image_generator=%s",
        (request.word or "").strip().lower(),
        request.verse_generator,
        request.image_generator,
    )
    try:
        result = mnemo_service.generate(request, user_id=user_id)
        logger.info(
            "[MNEMO] HTTP POST /mnemo/generate done word=%r cache_hit=%s image_url=%s",
            (request.word or "").strip().lower(),
            result.cache_hit,
            bool(result.image_url),
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

# Получение списка слов, для которых уже есть сохраненная мнемоника
@app.get(f"{settings.api_prefix}/mnemo/cache", response_model=list[str])
def list_cached_words(
    user_id: int = Depends(get_current_user_id),
    mnemo_service: MnemoService = Depends(get_service),
) -> list[str]:
    return mnemo_service.list_cached_words(user_id)

# Получение сохраненной мнемоники по слову
@app.get(f"{settings.api_prefix}/mnemo/cache/{{word}}", response_model=MnemoResponse)
def get_cached_mnemo(
    word: str,
    learning_lang: str = Query("en"),
    user_id: int = Depends(get_current_user_id),
    mnemo_service: MnemoService = Depends(get_service),
) -> MnemoResponse:
    cached = mnemo_service.get_cache(word, user_id=user_id, learning_lang=learning_lang)
    if cached is None:
        raise HTTPException(status_code=404, detail="Cached mnemonic not found")
    return cached

# Публичный доступ к изображению
@app.get(f"{settings.api_prefix}/mnemo/image/public/{{token}}")
def get_mnemo_image_public(token: str) -> Response:
    if not mnemo_cache_repo:
        raise HTTPException(status_code=503, detail="Database not configured")
    cached = mnemo_cache_repo.get_by_image_token(token.strip())
    if cached is None or not cached.image_data:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=cached.image_data, media_type=cached.image_content_type or "image/png")

# Получение изображения по слову
@app.get(f"{settings.api_prefix}/mnemo/image/{{word}}")
def get_mnemo_image(
    word: str,
    user_id: int = Depends(get_current_user_id),
) -> Response:
    if not mnemo_cache_repo:
        raise HTTPException(status_code=503, detail="Database not configured")
    cached = mnemo_cache_repo.get(user_id, word.strip())
    if cached is None or not cached.image_data:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=cached.image_data, media_type=cached.image_content_type or "image/png")

# Проверка статуса сервиса
@app.get(f"{settings.api_prefix}/health", response_model=HealthResponse)
def health(mnemo_service: MnemoService = Depends(get_service)) -> HealthResponse:
    return mnemo_service.health()

# Получение аватара
@app.get("/api/v1/auth/avatar-presets/{preset_name}")
async def get_avatar_preset(preset_name: str):
    preset_files = {
        "example-1": "avatar1.jpg",
        "example-2": "avatar2.jpg",
        "example-3": "avatar3.jpg",
        "example-4": "avatar4.jpg",
        "example-5": "avatar5.jpg",
    }

    if preset_name not in preset_files:
        return JSONResponse(status_code=404, content={"detail": "Preset not found"})

    filename = preset_files[preset_name]
    file_path = os.path.join("/app/avatar", filename)

    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="image/jpeg")
    svg_content = f'''<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
            <circle cx="50" cy="50" r="40" fill="#{hash(preset_name) % 0xFFFFFF:06x}" />
            <text x="50" y="55" font-size="20" text-anchor="middle" fill="white">{preset_name[-1]}</text>
        </svg>'''
    return Response(content=svg_content, media_type="image/svg+xml")

# Регистрация нового пользователя
@app.post(f"{settings.api_prefix}/auth/register", response_model=AuthResponse)
def register(request: RegisterRequest) -> AuthResponse:
    password = truncate_password_for_bcrypt(request.password)

    try:
        user = auth_store.create_user(
            email=request.email,
            password=password,
            username=request.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    token = create_token(
        {"sub": user["email"]},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )

    return AuthResponse(
        access_token=token,
        user=UserInfo(
            email=user["email"],
            username=user.get("username"),
            avatar_url=user.get("avatar_url"),
        ),
    )

# Вход существующего пользователя
@app.post(f"{settings.api_prefix}/auth/login", response_model=AuthResponse)
def login(request: LoginRequest) -> AuthResponse:
    password = truncate_password_for_bcrypt(request.password)
    user = auth_store.verify_user(request.email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(
        {"sub": user["email"]},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expire_minutes=settings.jwt_expire_minutes,
    )

    return AuthResponse(
        access_token=token,
        user=UserInfo(
            email=user["email"],
            username=user.get("username"),
            avatar_url=user.get("avatar_url"),
        ),
    )

# Получение информации о текущем пользователе по JWT токену
@app.get(f"{settings.api_prefix}/auth/me", response_model=UserInfo)
def auth_me(authorization: str | None = Header(None)) -> UserInfo:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization[7:].strip()
    payload = decode_token(token, settings.jwt_secret, settings.jwt_algorithm)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = str(payload["sub"]).strip().lower()
    user = auth_store.get_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return UserInfo(
        email=user["email"],
        username=user.get("username"),
        avatar_url=user.get("avatar_url"),
    )

# Обновление профиля
@app.patch(f"{settings.api_prefix}/auth/me", response_model=UserInfo)
def update_profile(
    body: UpdateProfileRequest,
    user_id: int = Depends(get_current_user_id),
) -> UserInfo:
    if not hasattr(auth_store, "update_avatar"):
        raise HTTPException(status_code=503, detail="Profile update requires PostgreSQL")

    if body.username is not None and hasattr(auth_store, "update_username"):
        auth_store.update_username(user_id, body.username)

    if body.email is not None and body.password and hasattr(auth_store, "update_email"):
        ok = auth_store.update_email(user_id, body.email, body.password)
        if not ok:
            raise HTTPException(status_code=400, detail="Invalid password or email already taken")

    if body.avatar_url is not None:
        auth_store.update_avatar(user_id, body.avatar_url)

    user = auth_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserInfo(
        email=user["email"],
        username=user.get("username"),
        avatar_url=user.get("avatar_url"),
    )

# Загрузка нового аватара
@app.post(f"{settings.api_prefix}/auth/me/avatar", response_model=UserInfo)
def upload_avatar(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
) -> UserInfo:
    if not hasattr(auth_store, "update_avatar_from_upload"):
        raise HTTPException(status_code=503, detail="Avatar upload requires PostgreSQL")

    ct = (file.content_type or "").strip().lower()
    if ct not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, WebP images are allowed")

    try:
        contents = file.file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    finally:
        file.file.close()

    ok = auth_store.update_avatar_from_upload(
        user_id=user_id,
        data=contents,
        content_type=ct,
        api_prefix=settings.api_prefix,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="User not found.")

    user = auth_store.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return UserInfo(
        email=user["email"],
        username=user.get("username"),
        avatar_url=user.get("avatar_url"),
    )

# Доступ к аватару по токену
@app.get(f"{settings.api_prefix}/auth/avatar/public/{{token}}")
def get_public_avatar(token: str) -> Response:
    if not hasattr(auth_store, "get_avatar_blob_by_public_token"):
        raise HTTPException(status_code=503, detail="Avatar storage requires PostgreSQL")

    blob = auth_store.get_avatar_blob_by_public_token(token)
    if not blob:
        raise HTTPException(status_code=404, detail="Avatar not found")

    data, media_type = blob
    return Response(content=data, media_type=media_type or "image/jpeg")

# Статистика
@app.get(f"{settings.api_prefix}/dictionary/stats")
def get_learning_stats(
    user_id: int = Depends(get_current_user_id),
):
    words_total = user_words_repo.count_by_user(user_id)

    created_at = auth_store.get_user_created_at(user_id)
    days_learning = 0
    if created_at:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        delta = now - created_at
        days_learning = max(0, delta.days)
    elif words_total > 0:
        days_learning = 1

    words_learned = user_words_repo.count_learned(user_id)

    return {
        "days_learning": days_learning,
        "words_total": words_total,
        "words_learned": words_learned,
    }

# Список категорий пользователя
@app.get(f"{settings.api_prefix}/dictionary/categories", response_model=list[str])
def list_dictionary_categories(
    user_id: int = Depends(get_current_user_id),
) -> list[str]:
    return user_words_repo.list_categories_by_user(user_id)

# Получение IPA транскрипции
@app.get(f"{settings.api_prefix}/dictionary/transcription", response_model=TranscriptionResponse)
def get_transcription(
    word: str = "",
    lang: str = Query(
        "en",
        description="Транскрипция",
        min_length=2,
        max_length=8,
    ),
) -> TranscriptionResponse:
    return TranscriptionResponse(
        transcription=get_ipa(word, lang=normalize_ipa_lang_code(lang)) or ""
    )

# Перевод слова через MyMemory API
@app.get(f"{settings.api_prefix}/dictionary/translation", response_model=TranslationResponse)
def get_translation(
    word: str = "",
    source_lang: str = Query(
        "en",
        description="Язык исходного слова",
        min_length=2,
        max_length=8,
    ),
    target_lang: str = Query(
        "ru",
        description="Язык перевода",
        min_length=2,
        max_length=8,
    ),
) -> TranslationResponse:
    w = (word or "").strip()
    if not w:
        return TranslationResponse(translation="")
    translated = fetch_mymemory_translation(w, source_lang=source_lang, target_lang=target_lang)
    return TranslationResponse(translation=translated or "")

# Синтез WAV-аудио произношения через eSpeak-ng
@app.get(f"{settings.api_prefix}/dictionary/pronunciation/audio")
def pronunciation_audio(
    word: str = "",
    lang: str = Query(
        "en",
        description="ISO 639-1",
        min_length=2,
        max_length=8,
    ),
) -> Response:
    wav = synthesize_word_wav_espeak(word, lang)
    if not wav:
        raise HTTPException(
            status_code=404,
            detail="Could not synthesize pronunciation",
        )
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=86400"},
    )

# Получение URL произношения
@app.get(f"{settings.api_prefix}/dictionary/pronunciation", response_model=PronunciationResponse)
def get_pronunciation(
    word: str = "",
    lang: str = Query(
        "en",
        description="Произношение",
        min_length=2,
        max_length=8,
    ),
) -> PronunciationResponse:
    w = (word or "").strip()
    if not w:
        raise HTTPException(status_code=400, detail="word is required")

    code = normalize_ipa_lang_code(lang)

    audio_url: str | None = None
    if code == "en":
        audio_url = _fetch_pronunciation_audio_url(w.lower())

    if not audio_url:
        qw = urllib.parse.quote(w)
        audio_url = (
            f"{settings.api_prefix}/dictionary/pronunciation/audio?"
            f"word={qw}&lang={urllib.parse.quote(code)}"
        )

    return PronunciationResponse(audio_url=audio_url)

# Декопозиция
@app.get(f"{settings.api_prefix}/dictionary/decompose", response_model=DecompositionResponse)
def get_decomposition(
    word: str = "",
    translation: str = "",
    lang: str = Query(
        "en",
        description="ISO 639-1 язык слова",
        min_length=2,
        max_length=8,
    ),
    user_id: int | None = Depends(get_optional_user_id),
) -> DecompositionResponse:
    w = (word or "").strip()
    t = (translation or "").strip()
    lc = normalize_ipa_lang_code(lang)

    dict_entry = (
        user_words_repo.get_by_user_and_word(user_id, w)
        if user_id is not None and w
        else None
    )

    try:
        logger.info(
            "[DICT] decompose request word=%r translation=%r lang=%s user_id=%s",
            w,
            t[:80] if t else "",
            lc,
            user_id,
        )

        if dict_entry is not None:
            cached = decomposition_cache_repo.get(dict_entry.id)
            if cached:
                logger.info(
                    "[DICT] decompose cache hit word=%r user_word_id=%s",
                    w,
                    dict_entry.id,
                )
                return DecompositionResponse(
                    word=w,
                    translation_ru=t,
                    parts=cached,
                )

        logger.info("[DICT] decompose running model/fallback word=%r lang=%s", w, lc)
        data = decompose_word(w, lang=lc)
        raw_parts = data.get("parts") or ([] if not w else [w])
        parts = raw_parts if isinstance(raw_parts, list) else ([] if not w else [w])
        parts = [str(p).strip() for p in parts if str(p).strip()]
        logger.info("[DICT] decompose done word=%r parts=%s", w, parts)

        if dict_entry is not None and parts and len(parts) >= 1:
            try:
                decomposition_cache_repo.save(dict_entry.id, parts)
                logger.info(
                    "[DICT] decompose saved to DB user_word_id=%s parts_count=%s",
                    dict_entry.id,
                    len(parts),
                )
            except Exception as exc:
                logger.warning("[DICT] decompose cache save failed: %s", exc)

        out_word = data.get("word", w)
        out_word_s = str(out_word).strip() if out_word else w

        return DecompositionResponse(
            word=out_word_s or w,
            translation_ru=t,
            parts=parts if parts else ([w] if w else []),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Decomposition failed: {exc}") from exc

# Список всех слов в словаре пользователя
@app.get(f"{settings.api_prefix}/dictionary/words", response_model=list[UserWordResponse])
def list_user_words(
    user_id: int = Depends(get_current_user_id),
) -> list[UserWordResponse]:
    entries = user_words_repo.list_by_user(user_id)

    parts_map: dict[int, list[str]] = {}
    if entries:
        parts_map = decomposition_cache_repo.get_batch([e.id for e in entries])

    out: list[UserWordResponse] = []
    for e in entries:
        plist = parts_map.get(e.id) if parts_map else None
        out.append(_user_word_response_from_orm(e, parts=plist))
    return out

# Слова, которые пора повторять
@app.get(f"{settings.api_prefix}/dictionary/words/due", response_model=list[UserWordResponse])
def list_dictionary_words_due(
    user_id: int = Depends(get_current_user_id),
) -> list[UserWordResponse]:
    entries = user_words_repo.list_due_by_user(user_id)
    if not entries:
        return []

    parts_map = decomposition_cache_repo.get_batch([e.id for e in entries])

    out: list[UserWordResponse] = []
    for e in entries:
        parts = parts_map.get(e.id)
        out.append(_user_word_response_from_orm(e, parts=parts))
    return out

# Добавление нового слова в словарь
@app.post(f"{settings.api_prefix}/dictionary/words", response_model=UserWordResponse)
def add_user_word(
    body: UserWordCreate,
    user_id: int = Depends(get_current_user_id),
) -> UserWordResponse:
    transcription = body.transcription or get_ipa(body.word, lang=body.word_language)

    entry = user_words_repo.add(
        user_id=user_id,
        word=body.word,
        translation=body.translation,
        is_favorite=body.is_favorite,
        transcription=transcription or None,
        category=body.category,
        word_language=body.word_language,
    )

    return _user_word_response_from_orm(entry)

# Обновление существующего слова
@app.patch(f"{settings.api_prefix}/dictionary/words/{{entry_id}}", response_model=UserWordResponse)
def update_user_word(
    entry_id: int,
    body: UserWordUpdate,
    user_id: int = Depends(get_current_user_id),
) -> UserWordResponse:
    word_to_use = body.word if body.word is not None else None
    transcription = body.transcription
    if word_to_use is not None and transcription is None:
        if body.word_language is not None:
            ipa_lang = normalize_ipa_lang_code(body.word_language)
        else:
            prev = user_words_repo.get(entry_id, user_id)
            ipa_lang = normalize_ipa_lang_code(
                getattr(prev, "word_language", None) if prev else None
            )
        transcription = get_ipa(word_to_use, lang=ipa_lang) or ""

    entry = user_words_repo.update(
        entry_id,
        user_id,
        word=body.word,
        translation=body.translation,
        is_favorite=body.is_favorite,
        transcription=transcription,
        category=body.category,
        is_learned=body.is_learned,
        word_language=body.word_language,
    )

    if entry is None:
        raise HTTPException(status_code=404, detail="Word not found")

    return _user_word_response_from_orm(entry)

# Применение оценки из карточки (SM-2 алгоритм)
@app.post(f"{settings.api_prefix}/dictionary/words/{{entry_id}}/srs-review", response_model=UserWordResponse)
def post_srs_review(
    entry_id: int,
    body: SrsReviewRequest,
    user_id: int = Depends(get_current_user_id),
) -> UserWordResponse:
    entry = user_words_repo.apply_srs_review(entry_id, user_id, body.quality)
    if entry is None:
        raise HTTPException(status_code=404, detail="Word not found")
    pmap = decomposition_cache_repo.get_batch([entry.id])
    parts = pmap.get(entry.id)
    return _user_word_response_from_orm(entry, parts=parts)

# Удаление слова из словаря
@app.delete(f"{settings.api_prefix}/dictionary/words/{{entry_id}}")
def delete_user_word(
    entry_id: int,
    user_id: int = Depends(get_current_user_id),
) -> None:
    if not user_words_repo.delete(entry_id, user_id):
        raise HTTPException(status_code=404, detail="Word not found")

# Экспорт карточек
@app.post(f"{settings.api_prefix}/dictionary/export/docx")
def export_dictionary_docx(
    body: ExportDocxRequest,
    user_id: int = Depends(get_current_user_id),
    mnemo_service: MnemoService = Depends(get_service),
) -> Response:
    blob = build_user_cards_docx(
        user_id=user_id,
        entry_ids=list(body.entry_ids),
        user_words_repo=user_words_repo,
        mnemo_cache_repo=mnemo_cache_repo,
        decomposition_cache_repo=decomposition_cache_repo,
        mnemo_service=mnemo_service,
        preset_assets_dir=_preset_assets_dir,
    )
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="mnemo-cards.docx"'},
    )