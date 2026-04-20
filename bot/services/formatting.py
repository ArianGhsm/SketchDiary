from __future__ import annotations

from html import escape
from typing import Iterable

from bot.services.localization import fa


def e(value: object) -> str:
    return escape(str(value), quote=False)


def code(value: object) -> str:
    return f"<code>{e(value)}</code>"


def bold(value: object) -> str:
    return f"<b>{e(value)}</b>"


def quote_lines(lines: Iterable[str]) -> str:
    prepared = [line for line in lines if line]
    if not prepared:
        return ""
    return "<blockquote>" + "\n".join(prepared) + "</blockquote>"


def labeled_row(icon: str, label: str, value: str) -> str:
    return f"{icon} <b>{e(label)}:</b> {value}"


def html_list(items: Iterable[str]) -> str:
    prepared = [item for item in items if item]
    return "\n".join(f"• {item}" for item in prepared)


def fa_code(value: object) -> str:
    return code(fa(str(value)))
