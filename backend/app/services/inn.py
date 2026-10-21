"""Проверка ИНН: длина и контрольные цифры (алгоритм ФНС)."""

from app.errors import ValidationFailed

_W10 = [2, 4, 10, 3, 5, 9, 4, 6, 8]
_W12_1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
_W12_2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]


def _check_digit(digits: list[int], weights: list[int]) -> int:
    return sum(d * w for d, w in zip(digits, weights, strict=False)) % 11 % 10


def is_valid_inn(inn: str) -> bool:
    if not inn.isdigit() or len(inn) not in (10, 12):
        return False
    d = [int(c) for c in inn]
    if len(inn) == 10:
        return _check_digit(d, _W10) == d[9]
    return _check_digit(d, _W12_1) == d[10] and _check_digit(d, _W12_2) == d[11]


def validate_inn(inn: str) -> str:
    """Возвращает очищенный ИНН или бросает понятную ошибку."""
    inn = inn.strip()
    if not inn.isdigit() or len(inn) not in (10, 12):
        raise ValidationFailed("ИНН должен состоять из 10 цифр (для компании) или 12 цифр (для ИП)")
    if not is_valid_inn(inn):
        raise ValidationFailed("В ИНН ошибка: не сходится контрольная цифра. Проверьте номер")
    return inn
