from enum import Enum
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

from data.messages import bot_messages

logger = logging.getLogger(__name__)
logger.setLevel("INFO")

QUERY_SEPARATOR = ":"
DEFAULT_CONTEXT = ContextTypes.DEFAULT_TYPE
UserDataT = TypeVar("UserDataT")


class QuizzTypeEnum(Enum):
    WORDS = "words"


@dataclass
class UserInfo:
    _field_name_ = "user_info"
    user_id: int
    chat_id: int
    user_token: str
    msg_to_delete: list[int] = field(default_factory=list)


@dataclass
class BotInfo:
    _field_name_ = "bot_info"
    active_bot_msg: int
    quizz_type: QuizzTypeEnum | None = None


@dataclass
class BotMenu:
    msg: str
    prefix: str
    buttons: list[tuple[str, str]] = field(default_factory=list)
    number: int = 2


main_bot_menu = BotMenu(
    msg=bot_messages["welcome"],
    prefix="main",
    buttons=[
        ("📚 Учить слова", QuizzTypeEnum.WORDS.value),
        ("📝 Статистика", "stats"),
        ("🔧 Настройки", "settings"),
    ],
)


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
        InlineKeyboardButton(ans[0], callback_data=f"{prefix}{QUERY_SEPARATOR}{ans[1]}")
        for ans in buttons
    ]
    keyboard = [
        answer_keys[button : button + number]
        for button in range(0, len(answer_keys), number)
    ]
    reply_in = InlineKeyboardMarkup(keyboard)
    return reply_in


def get_context_data(
    data_pack: Any | None, class_type: Type[UserDataT]
) -> UserDataT | None:
    if not data_pack or not isinstance(data_pack, Mapping):
        return None
    field_name = getattr(class_type, "_field_name_", None)
    if not field_name:
        logger.error(f"{class_type} must have a '_field_name_' class attribute")
        return None
    result_data = data_pack.get(field_name, None)
    return result_data if isinstance(result_data, class_type) else None


def set_context_data(
    data_pack: dict, data: UserDataT
) -> Mapping:
    field_name = getattr(data, "_field_name_", None)
    if not field_name:
        logger.error(f"{data} must have a '_field_name_' class attribute")
        return data_pack
    data_pack[field_name] = data
    return data_pack


def create_menu_markup(bot_menu: BotMenu) -> InlineKeyboardMarkup:
    return keyboard_in_maker(bot_menu.buttons, bot_menu.prefix, bot_menu.number)


def split_query(query: str) -> list[str]:
    return query.split(QUERY_SEPARATOR)
