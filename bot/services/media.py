from __future__ import annotations

from pathlib import Path

from aiogram.types import FSInputFile

from config import DEFAULT_VERIFICATION_PHOTO_PATH


def resolve_verification_photo(profile_photo_file_id: str | None):
    """Prefer the user's Telegram photo, then fall back to the local class image."""
    if profile_photo_file_id:
        return profile_photo_file_id

    fallback_path = Path(DEFAULT_VERIFICATION_PHOTO_PATH)
    if fallback_path.exists():
        return FSInputFile(fallback_path)

    return None
