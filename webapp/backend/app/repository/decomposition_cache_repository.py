# Файл для работы с таблицей декомпозиции слов

from __future__ import annotations

import json
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from app.core.database import WordDecomposition

# Функция для извлечения частей из словаря
def lookup_parts_by_entry_id(
    parts_map: dict[int, list[str]],
    entry_id: int,
) -> list[str] | None:
    parts = parts_map.get(entry_id)
    return parts if parts else None

# Класс для сохранения разбиения слов на части
class DecompositionCacheRepository:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    # Создаём новую сессию
    def _session(self) -> Session:
        return self._session_factory()
    
    # Получаем разбиение слова по ID записи user_word
    def get(self, user_word_id: int) -> list[str] | None:
        if user_word_id <= 0:
            return None

        with self._session() as session:
            # Ищем запись в таблице
            row = session.scalar(
                select(WordDecomposition).where(
                    WordDecomposition.user_word_id == user_word_id,
                )
            )
            if not row:
                return None
            
            # Десериализуем JSON строку в список Python
            try:
                parts = json.loads(row.parts_json)
                return parts if isinstance(parts, list) else None
            except (json.JSONDecodeError, TypeError):
                return None
            
    # Сохраняем разбиение слова
    def save(self, user_word_id: int, parts: list[str]) -> None:
        if user_word_id <= 0:
            return
        
        # Очищаем части
        parts_clean = [str(p).strip() for p in parts if p]
        if not parts_clean:
            return
        
        payload = json.dumps(parts_clean, ensure_ascii=False)

        with self._session() as session:
            stmt = (
                pg_insert(WordDecomposition)
                .values(user_word_id=user_word_id, parts_json=payload)
                .on_conflict_do_update(
                    index_elements=["user_word_id"],
                    set_={"parts_json": payload},
                )
            )
            session.execute(stmt)
            session.commit()

    # Получаем разбиение для нескольких слов за один запрос
    def get_batch(self, user_word_ids: list[int]) -> dict[int, list[str]]:
        result: dict[int, list[str]] = {}
        
        # Фильтруем
        ids = [i for i in user_word_ids if i and i > 0]
        if not ids:
            return result

        with self._session() as session:
            # Один запрос для всех ID
            rows = session.execute(
                select(WordDecomposition).where(
                    WordDecomposition.user_word_id.in_(ids),
                )
            ).scalars().all()

            # Преобразуем результат в словарь
            for cached in rows:
                try:
                    parts = json.loads(cached.parts_json)
                    if isinstance(parts, list):
                        result[int(cached.user_word_id)] = parts
                except (json.JSONDecodeError, TypeError):
                    continue
        return result