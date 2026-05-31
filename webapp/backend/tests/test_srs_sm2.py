# Тесты алгоритма SM-2

from app.services.srs_sm2 import DEFAULT_EF, EF_MIN, review_sm2, new_card_state, SrsCardState

# Новая карточка: EF=2.5, интервал 1 день, успешных повторений ещё нет
def test_new_card_defaults_match_spec() -> None:
    s = new_card_state()
    assert s.easiness == DEFAULT_EF == 2.5
    assert s.interval_days == 1
    assert s.repetitions == 0

# Первый успех (quality ≥ 3): repetitions=1, интервал остаётся 1 день
def test_new_card_first_success_gives_one_day() -> None:
    s = new_card_state()
    out = review_sm2(s, quality=4)
    assert out.repetitions == 1
    assert out.interval_days == 1
    assert out.easiness >= DEFAULT_EF - 0.3

# Второй успех подряд: фиксированный интервал 6 дней
def test_second_success_six_days() -> None:
    s = SrsCardState(easiness=2.5, interval_days=1, repetitions=1)
    out = review_sm2(s, quality=4)
    assert out.repetitions == 2
    assert out.interval_days == 6

# quality < 3 — провал: сброс счётчика и интервала, EF не меняется
def test_fail_resets() -> None:
    s = SrsCardState(easiness=2.5, interval_days=14, repetitions=5)
    out = review_sm2(s, quality=1)
    assert out.repetitions == 0
    assert out.interval_days == 1
    assert out.easiness == 2.5

# С третьего успеха интервал = round(предыдущий × EF)
def test_third_success_uses_product() -> None:
    s = SrsCardState(easiness=2.5, interval_days=6, repetitions=2)
    out = review_sm2(s, quality=4)
    assert out.repetitions == 3
    assert out.interval_days >= 10

# При quality=5 EF увеличивается +0.1
def test_easiness_formula_quality_five_increases_by_point_one() -> None:
    s = SrsCardState(easiness=2.5, interval_days=6, repetitions=2)
    out = review_sm2(s, quality=5)
    assert out.easiness == 2.6

# EF не опускается ниже EF_MIN даже при слабой оценке
def test_easiness_never_below_minimum() -> None:
    s = SrsCardState(easiness=EF_MIN, interval_days=6, repetitions=2)
    out = review_sm2(s, quality=3)
    assert out.easiness == EF_MIN
