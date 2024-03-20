from dataclasses import dataclass, field
import logging
import random
import string
from typing import Any, Iterable, Mapping, Type, TypeVar

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


DEFAULT_CONTEXT = ContextTypes.DEFAULT_TYPE
UserDataT = TypeVar("UserDataT")


@dataclass
class UserInfo:
    _field_name_ = "user_info"
    chat_id: int
    user_token: str


def random_lower_string(str_len: int = 32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=str_len))


def random_email() -> str:
    return f"{random_lower_string(20)}@{random_lower_string(6)}.com"


def keyboard_maker(buttons, number):
    keyboard = [
        buttons[button : button + number] for button in range(0, len(buttons), number)
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    return markup


def keyboard_in_maker(
    buttons: Iterable, prefix: str, number: int
) -> InlineKeyboardMarkup:
    answer_keys = [
        InlineKeyboardButton(ans[0], callback_data=f"{prefix}:{ans[1]}")
        for ans in buttons
    ]
    keyboard = [
        answer_keys[button : button + number]
        for button in range(0, len(answer_keys), number)
    ]
    reply_in = InlineKeyboardMarkup(keyboard)
    return reply_in


def get_user_info(
    user_data: Any | None, class_type: Type[UserDataT]
) -> UserDataT | None:
    if not user_data or not isinstance(user_data, Mapping):
        return None
    field_name = getattr(class_type, "_field_name_", None)
    if not field_name:
        logger.error(f"{class_type} must have a '_field_name_' class attribute")
        return None
    user_info = user_data.get(field_name, None)
    return user_info if isinstance(user_info, class_type) else None
