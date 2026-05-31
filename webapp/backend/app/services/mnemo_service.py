# Файл сервиса мнемоники

from __future__ import annotations
from app.core import Settings
from app.domain import MnemoDomainEngine
from app.repository.decomposition_cache_repository import DecompositionCacheRepository
from app.repository.mnemo_cache_repository import WordMnemoRepository
from app.repository.user_words_repository import UserWordsRepository
from app.schemas.mnemo import GenerateMnemoRequest, HealthResponse, MnemoResponse

# Класс для всех операций с мнемоникой
class MnemoService:
    # Инициализация
    def __init__(
        self,
        settings: Settings,
        mnemo_cache_repo: WordMnemoRepository | None = None,
        decomposition_cache_repo: DecompositionCacheRepository | None = None,
        user_words_repo: UserWordsRepository | None = None,
    ):
        self.settings = settings
        # Создаем движок
        self.domain = MnemoDomainEngine(
            settings,
            mnemo_cache_repo=mnemo_cache_repo,
            decomposition_cache_repo=decomposition_cache_repo,
            user_words_repo=user_words_repo,
        )

    # Генерируем мнемонику
    def generate(self, request: GenerateMnemoRequest, *, user_id: int) -> MnemoResponse:
        return self.domain.generate(request, user_id=user_id)

    # Получаем кэшированную мнемонику для слова
    def get_cache(self, word: str, *, user_id: int, learning_lang: str = "en") -> MnemoResponse | None:
        return self.domain.get_cache(word, user_id=user_id, learning_lang=learning_lang)

    # Возвращаем список слов, для которых есть кэшированная мнемоника
    def list_cached_words(self, user_id: int) -> list[str]:
        return self.domain.list_cached_words(user_id)
    
    # Проверяем состояние сервиса
    def health(self) -> HealthResponse:
        return self.domain.health()
