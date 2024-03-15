import logging
import os
import random
import string
from dataclasses import dataclass
from enum import IntEnum, Enum, auto
from functools import partial
from time import sleep

import requests
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    User,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL")


class StateEnum(IntEnum):
    CHOOSING_ACT = auto()
    WORD_PLAY = auto()


def random_lower_string(str_len: int = 32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=str_len))


def random_email() -> str:
    return f"{random_lower_string(20)}@{random_lower_string(6)}.com"


def get_bot_token(bot_email, bot_pass):
    """Get bot token for the api"""
    api_token = ""
    while not api_token:
        url = f"{API_URL}/login/access-token"
        data = {"username": bot_email, "password": bot_pass}
        token = None
        try:
            res = requests.post(url, data=data)
            token = res.json()
            res.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.error(f"ConnectionError in bot api token gen :: {token}")
            sleep(2)

        else:
            api_token = res.json()["access_token"]
    return api_token


def keyboard_maker(buttons, number):
    keyboard = [
        buttons[button : button + number] for button in range(0, len(buttons), number)
    ]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    return markup


async def get_user_token(
    user_id: int, context: ContextTypes.DEFAULT_TYPE
) -> str | None:
    user_token = None
    if not context or not context.user_data:
        return None

    user_token = context.user_data.get("user_token")
    bot_token = context.bot_data.get("bot_token")
    if not user_token:
        url = f"{API_URL}/login/access-token-bot"
        headers = {"Authorization": f"Bearer {bot_token}"}
        data = {"tg_id": user_id}
        try:
            res = requests.post(url, data=data, headers=headers)
            res.raise_for_status()
        except Exception:
            return None
        else:
            user_token = res.json()["access_token"]
            context.user_data["user_toker"] = user_token

    return user_token


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for input."""
    if not update.message or not update.message.from_user:
        return ConversationHandler.END

    user_id = update.message.from_user.id
    if not user_id:
        return ConversationHandler.END
    user_token = get_user_token(user_id, context)
    if not user_token:
        await update.message.reply_text("You do not have a token")
    await update.message.reply_text(f"Success!! {user_id}")
    return StateEnum.CHOOSING_ACT


async def cancel(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    if not update.message or not update.message.from_user:
        return ConversationHandler.END

    user = update.message.from_user
    logger.info("User %s canceled the conversation.", user.first_name)
    await update.message.reply_text("Good by!", reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    logger.info("bot :: start")
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        return None
    logger.info("bot token :: finish")
    application = Application.builder().token(bot_token).build()

    logger.info("bot api token :: start")
    bot_email = os.getenv("BOT_EMAIL")
    bot_pass = os.getenv("BOT_PASS")
    api_token = get_bot_token(bot_email, bot_pass)
    logger.info("bot api token :: finish")
    if not api_token:
        logger.info("bot api token :: empty")
        return None

    application.bot_data["api_token"] = api_token

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            StateEnum.CHOOSING_ACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
