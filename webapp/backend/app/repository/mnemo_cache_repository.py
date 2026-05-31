# Файл для работы с таблицей мнемоники

from __future__ import annotations

import secrets
from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session
from app.core.database import WordMnemo
from app.core.database import UserWord
from app.schemas.mnemo import VERSE_LEARNING_LANGUAGE_CODES


def _normalize_mnemo_cache_learning_lang(raw: object) -> str:
    ll = str(raw or "en").strip().lower()
    if len(ll) > 2:
        ll = ll[:2]
    return ll if ll in VERSE_LEARNING_LANGUAGE_CODES else "en"

# Класс для хранения мнемокарточек
class WordMnemoRepository:
    def __init__(self, session_factory, user_words_repo=None) -> None:
        self._session_factory = session_factory
        self._user_words = user_words_repo

    # Создаём новую сессию
    def _session(self) -> Session:
        return self._session_factory()

    # Преобразуем user_id, word в user_word_id
    def _resolve_user_word_id(self, user_id: int, word: str) -> int | None:
        if user_id <= 0 or self._user_words is None:
            return None
        entry = self._user_words.get_by_user_and_word(user_id, word)
        return entry.id if entry else None
    
    # Получаем сохраненную мнемокарточку для слова
    def get(
        self, user_id: int, word: str, *, learning_lang: str = "en"
    ) -> WordMnemo | None:
        w = (word or "").strip().lower()
        if not w:
            return None

        # Находим ID слова в таблице user_words
        uid = self._resolve_user_word_id(user_id, w)
        if uid is None:
            return None

        ll = _normalize_mnemo_cache_learning_lang(learning_lang)

        with self._session() as session:
            row = session.scalar(
                select(WordMnemo).where(
                    WordMnemo.user_word_id == uid,
                    WordMnemo.learning_lang == ll,
                )
            )
            return session.scalar(
                select(WordMnemo)
                .where(WordMnemo.user_word_id == uid)
                .order_by(desc(WordMnemo.id))
                .limit(1)
            )
        
    # Получаем мнемокарточку по публичному токену картинки
    def get_by_image_token(self, token: str) -> WordMnemo | None:
        t = (token or "").strip()
        if not t or len(t) > 128:
            return None

        with self._session() as session:
            return session.scalar(select(WordMnemo).where(WordMnemo.image_public_token == t))
        
    # Возвращаем список слов, для которых есть сохраненная мнемоника
    def list_words(self, user_id: int) -> list[str]:
        if user_id <= 0:
            return []

        with self._session() as session:
            rows = session.execute(
                select(UserWord.word)
                .join(WordMnemo, WordMnemo.user_word_id == UserWord.id)
                .where(UserWord.user_id == user_id)
                .distinct()
            ).scalars().all()
            return [r for r in rows if r]
        
    # Удаляем сохраненную карточку для слова
    def delete_for_user_word(self, user_id: int, word: str) -> None:
        w = (word or "").strip().lower()
        if not w or user_id <= 0:
            return

        uid = self._resolve_user_word_id(user_id, w)
        if uid is None:
            return

        with self._session() as session:
            session.execute(delete(WordMnemo).where(WordMnemo.user_word_id == uid))
            session.commit()

    # Сохраняем мнемокарточку
    def save(
        self,
        *,
        user_id: int,
        word: str,
        mnemonic_phrase_ru: str,
        image_data: bytes | None = None,  
        image_content_type: str | None = None,
        image_url: str | None = None,     
        learning_lang: str = "en", 
    ) -> None:
        w = (word or "").strip().lower()
        ll = _normalize_mnemo_cache_learning_lang(learning_lang)

        if not w or user_id <= 0:
            return

        uid = self._resolve_user_word_id(user_id, w)
        if uid is None:
            return

        # Генерируем публичный токен для картинки
        img_tok: str | None
        if image_data:
            img_tok = secrets.token_hex(32)
        else:
            img_tok = None

        with self._session() as session:
            # Проверяем, есть ли уже запись
            existing = session.scalar(
                select(WordMnemo).where(
                    WordMnemo.user_word_id == uid,
                    WordMnemo.learning_lang == ll,
                )
            )

            if existing:
                # UPDATE: обновляем существующую запись
                existing.mnemonic_phrase_ru = mnemonic_phrase_ru
                existing.image_data = image_data
                existing.image_content_type = image_content_type
                existing.image_public_token = img_tok
                if image_url is not None:
                    existing.image_url = image_url
            else:
                # INSERT: создаём новую запись
                session.add(
                    WordMnemo(
                        user_word_id=uid,
                        learning_lang=ll,
                        mnemonic_phrase_ru=mnemonic_phrase_ru,
                        image_url=image_url,
                        image_data=image_data,
                        image_content_type=image_content_type,
                        image_public_token=img_tok,
                    )
                )
            session.commit()