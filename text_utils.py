from __future__ import annotations


EN_TO_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
FA_AR_TO_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_persian_text(text: str) -> str:
    return str(text).translate(EN_TO_FA_DIGITS)


def normalize_numeric_input(text: str) -> str:
    return str(text).translate(FA_AR_TO_EN_DIGITS).strip()
