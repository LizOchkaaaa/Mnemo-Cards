# Файл для работы со словами пользователя

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session, joinedload
from app.core.database import UserWord
from app.core.database import SrsState
from app.services.ipa_word import normalize_ipa_lang_code
from app.services.srs_sm2 import DEFAULT_EF, SrsCardState, new_card_state, review_sm2

# Получаем состояние SRS из ORM-объекта
def _srs_state_from_loaded(entry: UserWord) -> SrsCardState:
    # Пытаемся получить связанный объект srs_state
    sr = getattr(entry, "srs_state", None)
    # Если нет или отсутствуют нужные поля
    if sr is None or getattr(sr, "srs_easiness", None) is None:
        return new_card_state()
    # Возвращаем текущее состояние
    return SrsCardState(
        easiness=float(sr.srs_easiness),               # Коэффициент лёгкости
        interval_days=int(sr.srs_interval_days or 1),  # Интервал в днях
        repetitions=int(sr.srs_repetitions or 0),      # Количество повторений
    )

# Класс для работы со словами пользователя в базе данных
class UserWordsRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    # Создаём новую сессию
    def _session(self) -> Session:
        return self._session_factory()
    
    # Возвращаем все слова пользователя
    def list_by_user(self, user_id: int) -> list[UserWord]:
        with self._session() as session:
            rows = session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(UserWord.user_id == user_id)
                .order_by(UserWord.word)
            ).scalars().unique().all()
            return list(rows)
        
    # Возвращаем категории пользователя
    def list_categories_by_user(self, user_id: int) -> list[str]:
        with self._session() as session:
            rows = session.execute(
                select(distinct(UserWord.category))
                .where(
                    UserWord.user_id == user_id,
                    UserWord.category.isnot(None),   
                    UserWord.category != "",
                )
                .order_by(UserWord.category)
            ).scalars().all()
            return [r for r in rows if r and len(r.strip()) > 1]

    # Возвращаем слова, которые нужно повторить
    def list_due_by_user(self, user_id: int) -> list[UserWord]:
        now = datetime.now(timezone.utc)

        with self._session() as session:
            rows = session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .join(SrsState, SrsState.user_word_id == UserWord.id)
                .where(
                    UserWord.user_id == user_id,
                    or_(
                        SrsState.srs_next_review_at.is_(None),
                        SrsState.srs_next_review_at <= now,
                    ),
                )
                .order_by(UserWord.word)
            ).unique().scalars().all()
            return list(rows)
        
    # Проверяем на дубликат
    def get_by_user_and_word(self, user_id: int, word: str) -> UserWord | None:
        w = (word or "").strip().lower()
        if not w:
            return None

        with self._session() as session:
            row = session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(
                    UserWord.user_id == user_id,
                    func.lower(UserWord.word) == w,
                )
            ).unique().scalar_one_or_none()
            return row

    # Находим слово по ID
    def get(self, entry_id: int, user_id: int) -> UserWord | None:
        with self._session() as session:
            row = session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(
                    UserWord.id == entry_id,
                    UserWord.user_id == user_id,
                )
            ).unique().scalar_one_or_none()
            return row

    # Добавляем новое слово в словарь пользователя
    def add(
        self,
        user_id: int,
        word: str,
        translation: str,
        is_favorite: bool = False,
        transcription: str | None = None,
        category: str | None = None,
        word_language: str | None = None,
    ) -> UserWord:
        with self._session() as session:
            now = datetime.now(timezone.utc)
            wl = normalize_ipa_lang_code(word_language)

            # Создаём запись слова
            entry = UserWord(
                user_id=user_id,
                word=word.strip(),
                translation=translation.strip(),
                is_favorite=is_favorite,
                transcription=(transcription or "").strip() or None,
                category=(category or "").strip() or None,
                word_language=wl,
                is_learned=False,
            )
            
            # Создаём начальное состояние SRS
            entry.srs_state = SrsState(
                srs_easiness=DEFAULT_EF,      # 2.5
                srs_interval_days=1,          # повторять через 1 день
                srs_repetitions=0,            # 0 повторений
                srs_next_review_at=now,       # повторить сегодня
            )
            
            session.add(entry)
            session.commit()
            session.refresh(entry)

            # Возвращаем запись с подгруженным SRS
            return session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(UserWord.id == entry.id)
            ).unique().scalar_one()
        
    # Применяем оценку пользователя к слову и пересчитываем интервал повторения
    def apply_srs_review(self, entry_id: int, user_id: int, quality: int) -> UserWord | None:
        q = max(0, min(5, int(quality)))

        with self._session() as session:
            # Находим слово
            entry = session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(
                    UserWord.id == entry_id,
                    UserWord.user_id == user_id,
                )
            ).unique().scalar_one_or_none()

            if not entry:
                return None

            # Получаем текущее состояние SRS
            state = _srs_state_from_loaded(entry)
            
            # Применяем алгоритм SM-2
            new_state = review_sm2(state, q)

            # Обновляем SRS запись
            sr = entry.srs_state
            if sr is None:
                sr = SrsState(user_word_id=entry.id)
                entry.srs_state = sr

            sr.srs_easiness = new_state.easiness
            sr.srs_interval_days = new_state.interval_days
            sr.srs_repetitions = new_state.repetitions
            sr.srs_next_review_at = datetime.now(timezone.utc) + timedelta(
                days=new_state.interval_days
            )

            # Если оценка больше 3, считаем слово выученным
            entry.is_learned = q >= 3

            session.commit()
            session.refresh(entry)
            
            # Возвращаем обновлённую запись
            return session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(UserWord.id == entry.id)
            ).unique().scalar_one()

    # Обновляем поля существующего слова
    def update(
        self,
        entry_id: int,
        user_id: int,
        *,
        word: str | None = None,
        translation: str | None = None,
        is_favorite: bool | None = None,
        transcription: str | None = None,
        category: str | None = None,
        is_learned: bool | None = None,
        word_language: str | None = None,
    ) -> UserWord | None:
        with self._session() as session:
            entry = session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(
                    UserWord.id == entry_id,
                    UserWord.user_id == user_id,
                )
            ).unique().scalar_one_or_none()

            if not entry:
                return None

            # Обновляем только переданные поля
            if word is not None:
                entry.word = word.strip()
            if translation is not None:
                entry.translation = translation.strip()
            if is_favorite is not None:
                entry.is_favorite = is_favorite
            if transcription is not None:
                entry.transcription = transcription.strip() or None
            if category is not None:
                entry.category = category.strip() or None
            if is_learned is not None:
                entry.is_learned = is_learned
            if word_language is not None:
                entry.word_language = normalize_ipa_lang_code(word_language)

            session.commit()
            session.refresh(entry)
            
            return session.execute(
                select(UserWord)
                .options(joinedload(UserWord.srs_state))
                .where(UserWord.id == entry.id)
            ).unique().scalar_one()
        
    # Удаляем слово из словаря пользователя
    def delete(self, entry_id: int, user_id: int) -> bool:
        with self._session() as session:
            entry = session.execute(
                select(UserWord).where(
                    UserWord.id == entry_id,
                    UserWord.user_id == user_id,
                )
            ).scalar_one_or_none()

            if not entry:
                return False

            session.delete(entry)
            session.commit()
            return True
    
    # Возвращаем общее количество слов пользователя
    def count_by_user(self, user_id: int) -> int:
        with self._session() as session:
            r = session.execute(
                select(func.count(UserWord.id)).where(UserWord.user_id == user_id)
            ).scalar_one()
            return r or 0
    
    # Возвращаем количество выученных слов
    def count_learned(self, user_id: int) -> int:
        with self._session() as session:
            r = session.execute(
                select(func.count(UserWord.id)).where(
                    UserWord.user_id == user_id,
                    UserWord.is_learned == True,
                )
            ).scalar_one()
            return r or 0