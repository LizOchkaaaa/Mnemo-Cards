# Файл для создания и настройки всех таблиц базы данных PostgreSQL

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,  
    Text, 
    UniqueConstraint, 
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


# Базовый класс
Base = declarative_base()

# Два числа для advisory lock
_SCHEMA_ADVISORY_LOCK = (712_384_941, 293_847_102)

# Создаём движок SQLAlchemy для подключения к PostgreSQL
def get_engine(database_url: str):
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

# Создаём таблицы по ORM-моделям
def init_db(engine) -> None:
    k1, k2 = _SCHEMA_ADVISORY_LOCK
    with engine.connect() as conn:
        conn.execute(text(f"SELECT pg_advisory_lock({k1}, {k2})"))
        conn.commit()
        try:
            # Создание
            Base.metadata.create_all(bind=conn)
            conn.commit()
        finally:
            try:
                conn.execute(text(f"SELECT pg_advisory_unlock({k1}, {k2})"))
                conn.commit()
            except Exception:
                pass

# Создаём фабрику сессий для работы
def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Таблица пользователей
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_avatar_public_token",
            "avatar_public_token",
            unique=True,
            postgresql_where=text("avatar_public_token IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)                             # ID
    email = Column(String(255), unique=True, nullable=False, index=True)                   # Почта
    username = Column(String(100), nullable=True)                                          # Имя пользователя
    password_hash = Column(String(255), nullable=False)                                    # Хэш пароля
    avatar_url = Column(Text, nullable=True)                                               # Внешняя ссылка на аватар
    avatar_data = Column(LargeBinary, nullable=True)                                       # Бинарные данные аватара
    avatar_type = Column(String(64), nullable=True)                                        # MIME тип
    avatar_public_token = Column(String(64), nullable=True)                                # Публичный токен для доступа
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True) # Дата регистрации

# Таблица слов
class UserWord(Base):
    __tablename__ = "user_words"

    id = Column(Integer, primary_key=True, autoincrement=True)                                         # ID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # Владелец
    word = Column(String(255), nullable=False)                                                         # Слово
    translation = Column(String(512), nullable=False)                                                  # Перевод
    transcription = Column(String(255), nullable=True)                                                 # IPA транскрипция
    category = Column(String(100), nullable=True)                                                      # Категория
    word_language = Column(String(10), nullable=False, server_default="en")                            # Язык слова
    is_favorite = Column(Boolean, default=False, nullable=False)                                       # В избранном?
    is_learned = Column(Boolean, default=False, nullable=False)                                        # Выучено?

    # Связь с SRS
    srs_state = relationship(
        "SrsState",
        back_populates="user_word",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

# Таблица для SM-2
class SrsState(Base):
    __tablename__ = "srs_states"
    __table_args__ = (
        Index("idx_srs_states_next_review", "srs_next_review_at"),        # поиск по дате
        Index("idx_srs_join_due", "user_word_id", "srs_next_review_at"),  # составной индекс
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_word_id = Column(
        Integer,
        ForeignKey("user_words.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    srs_easiness = Column(Float, nullable=True) 
    srs_interval_days = Column(Integer, nullable=True)   
    srs_repetitions = Column(Integer, nullable=True)      
    srs_next_review_at = Column(DateTime(timezone=True), nullable=True)

    user_word = relationship("UserWord", back_populates="srs_state")

# Таблица декомпозиции
class WordDecomposition(Base):
    __tablename__ = "word_decomposition"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_word_id = Column(
        Integer,
        ForeignKey("user_words.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    parts_json = Column(Text, nullable=False)


# Таблица мнемоники
class WordMnemo(Base):
    __tablename__ = "word_mnemo"
    __table_args__ = (
        UniqueConstraint(
            "user_word_id",
            "learning_lang",
            name="uq_mnemo_cache_user_word_learning",
        ),
        Index(
            "uq_mnemo_cache_image_public_token",
            "image_public_token",
            unique=True,
            postgresql_where=text("image_public_token IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_word_id = Column(
        Integer,
        ForeignKey("user_words.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    learning_lang = Column(String(10), nullable=False, default="en") # Язык обучения
    mnemonic_phrase_ru = Column(String(512), nullable=False)         # Стихотворение
    image_url = Column(Text, nullable=True)                          # Внешняя ссылка
    image_data = Column(LargeBinary, nullable=True)                  # Бинарные данные
    image_content_type = Column(String(64), nullable=True)           # MIME тип
    image_public_token = Column(String(64), nullable=True)           # Публичный токен

DecompositionCache = WordDecomposition
