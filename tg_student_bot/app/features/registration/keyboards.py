from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.core.callbacks import RegCb


def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ تأیید", callback_data=RegCb(action="confirm_yes").pack())
    kb.button(text="❌ عدم تأیید", callback_data=RegCb(action="confirm_no").pack())
    kb.adjust(2)
    return kb.as_markup()
