# Файл для реализации алгоритма SM-2 (SuperMemo 2)

from __future__ import annotations
from dataclasses import dataclass

# Минимальный фактор лёгкости
EF_MIN = 1.3
# Стартовый EF для новой карточки
DEFAULT_EF = 2.5

# Состояние карточки
@dataclass(frozen=True)
class SrsCardState:
    easiness: float     # EF
    interval_days: int  # Текущий интервал до следующего показа
    repetitions: int    # Число успешных повторений подряд

# Формула
def _update_easiness(ef: float, quality: int) -> float:
    q = max(0, min(5, quality))
    delta = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    new_ef = ef + delta
    return max(EF_MIN, float(new_ef))

#  Один шаг повторения по SM-2
def review_sm2(
    state: SrsCardState,
    quality: int,
) -> SrsCardState:
    q = max(0, min(5, int(quality)))
    ef = state.easiness
    prev_interval = max(1, state.interval_days)
    n = state.repetitions

    if q < 3:
        # Провал: интервал снова 1 день, успешные повторения обнуляются
        return SrsCardState(easiness=ef, interval_days=1, repetitions=0)

    new_ef = _update_easiness(ef, q)
    new_n = n + 1

    if new_n == 1:
        new_interval = 1
    elif new_n == 2:
        new_interval = 6
    else:
        new_interval = max(1, round(prev_interval * new_ef))

    return SrsCardState(easiness=new_ef, interval_days=new_interval, repetitions=new_n)

# Начальное состояние до первого успешного повторения
def new_card_state() -> SrsCardState:
    return SrsCardState(easiness=DEFAULT_EF, interval_days=1, repetitions=0)
