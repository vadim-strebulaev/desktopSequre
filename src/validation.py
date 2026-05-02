from __future__ import annotations

import re


_CARD_RE = re.compile(r"^[0-9A-Za-z-]{3,32}$")
_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё-]{2,40}$")
_PLATE_RE = re.compile(r"^[0-9A-Za-zА-Яа-яЁё- ]{4,16}$")


def validate_card_number(value: str) -> str:
    value = value.strip()
    if not _CARD_RE.match(value):
        raise ValueError("Номер пропуска: 3-32 символа (буквы/цифры/дефис).")
    return value


def validate_name(value: str, field: str) -> str:
    value = value.strip()
    if not _NAME_RE.match(value):
        raise ValueError(f"{field}: 2-40 букв (рус/лат) или дефис.")
    return value


def validate_positive_int(value: str, field: str, max_value: int = 24 * 30) -> int:
    value = value.strip()
    if not value.isdigit():
        raise ValueError(f"{field}: требуется целое число.")
    num = int(value)
    if num <= 0 or num > max_value:
        raise ValueError(f"{field}: должно быть 1..{max_value}.")
    return num


def validate_plate(value: str) -> str:
    value = value.strip()
    if not _PLATE_RE.match(value):
        raise ValueError("Номер авто: 4-16 символов.")
    return value

