from __future__ import annotations

from config import ADMIN_IDS, MAIN_REP_STUDENT_NUMBER, MAIN_REP_TELEGRAM_ID
from db import get_active_registration_by_tg_id, list_representatives
from text_utils import normalize_numeric_input


def normalize_student_number(value: str) -> str:
    normalized = normalize_numeric_input(value)
    return "".join(ch for ch in normalized if ch.isdigit())


def to_int_id(value) -> int | None:
    if value is None:
        return None
    digits = normalize_student_number(str(value))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def normalized_admin_ids() -> set[int]:
    normalized = set()
    for raw_id in ADMIN_IDS:
        parsed = to_int_id(raw_id)
        if parsed is not None:
            normalized.add(parsed)
    rep_id = to_int_id(MAIN_REP_TELEGRAM_ID)
    if rep_id is not None:
        normalized.add(rep_id)
    return normalized


def representative_user_ids() -> set[int]:
    ids = set()
    for row in list_representatives():
        ids.add(int(row["telegram_user_id"]))
    return ids


def is_admin(user_id: int) -> bool:
    return user_id in normalized_admin_ids()


def is_rep_candidate(user_id: int) -> bool:
    return user_id in representative_user_ids()


def is_verified_user(user_id: int) -> bool:
    return get_active_registration_by_tg_id(user_id) is not None


def is_verified_representative(user_id: int) -> bool:
    if not is_rep_candidate(user_id):
        return False
    registered = get_active_registration_by_tg_id(user_id)
    return bool(registered)


def verification_reviewer_ids() -> list[int]:
    return sorted(representative_user_ids() | normalized_admin_ids())
