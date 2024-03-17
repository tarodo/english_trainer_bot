import logging
import os
import random
import string
from dataclasses import dataclass
from enum import IntEnum, Enum, auto
from functools import partial
from time import sleep
from typing import Iterable

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

from core import get_wordsets, get_wordset_quiz

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")

API_URL = os.getenv("API_URL", "")


class StateEnum(IntEnum):
    CHOOSING_ACT = auto()
    CHOOSING_WORDSET = auto()
    WORD_PLAY = auto()


def random_lower_string(str_len: int = 32) -> str:
    return "".join(random.choices(string.ascii_lowercase, k=str_len))


def random_email() -> str:
    return f"{random_lower_string(20)}@{random_lower_string(6)}.com"


def get_bot_token(bot_email, bot_pass):
    """Get bot token for the api"""
    logger.debug("bot api token :: start")
    api_token = ""
    while not api_token:
        url = f"{API_URL}/login/access-token"
        data = {"username": bot_email, "password": bot_pass}
        try:
            logger.debug(f"bot api token :: {url=} :: {data=}")
            res = requests.post(url, data=data)
            res.raise_for_status()
            api_token = res.json()["access_token"]
            logger.debug(f"bot api token :: {api_token}")
        except requests.exceptions.ConnectionError:
            logger.error("ConnectionError in bot api token gen")
            sleep(2)
    return api_token


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


async def get_user_token(user_id: int, bot_token: str) -> str | None:
    logger.debug("user api token :: start")
    url = f"{API_URL}/login/access-token-bot"
    headers = {"Authorization": f"Bearer {bot_token}"}
    data = {"tg_id": user_id}
    res_body = None
    try:
        logger.debug(f"user api token :: {url=} : {data=} :: {headers=}")
        res = requests.post(url, json=data, headers=headers)
        res.raise_for_status()
        user_token = res.json()["access_token"]
        logger.debug(f"user api token :: {user_token}")
    except Exception:
        logger.debug(f"user api token :: empty :: {res_body}")
        return None
    logger.debug("user api token :: finish")
    return user_token


async def reg_user(user_id: int, bot_token: str) -> str | None:
    logger.debug("user reg :: start")
    url = f"{API_URL}/users/"
    headers = {"Authorization": f"Bearer {bot_token}"}
    data = {
        "email": random_email(),
        "tg_id": user_id,
        "password": random_lower_string(),
    }
    res_body = None
    try:
        logger.debug(f"user reg :: {url=} : {data=} :: {headers=}")
        res = requests.post(url, json=data, headers=headers)
        res_body = res.text
        res.raise_for_status()
        return await get_user_token(user_id, bot_token)
    except Exception:
        logger.debug(f"user reg :: empty :: {res_body}")
        return None


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send first question for the user"""
    if not update.message or not update.message.from_user:
        return ConversationHandler.END
    if not context or not context.user_data:
        return ConversationHandler.END

    text = "Hello my friend! What do you want from me?"
    buttons = (
        (
            "Words",
            "words",
        ),
    )
    markup = keyboard_in_maker(buttons, "main", 2)
    new_message = await update.message.reply_text(
        text,
        reply_markup=markup,
    )
    context.user_data["stat_msg_id"] = new_message.message_id
    context.user_data["quizz_msg_id"] = None

    return StateEnum.CHOOSING_ACT


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for input."""
    if not update.message or not update.message.from_user:
        return ConversationHandler.END
    if not context:
        return ConversationHandler.END

    user_id = update.message.from_user.id
    if not user_id:
        return ConversationHandler.END

    chat_id = update.message.chat_id
    if context.user_data is None:
        return ConversationHandler.END
    context.user_data["chat_id"] = chat_id

    msg_id = update.message.message_id
    await context.bot.delete_message(chat_id, msg_id)

    user_token = context.user_data.get("user_token") if context.user_data else None
    bot_token = context.bot_data.get("bot_token") if context.bot_data else None
    logger.debug(f"start :: {user_token=} :: {bot_token=}")
    if not user_token and bot_token:
        user_token = await get_user_token(user_id, bot_token)
    if user_token:
        if context.user_data is None:
            return ConversationHandler.END
        context.user_data["user_token"] = user_token

    if not user_token:
        await update.message.reply_text("Sorry. You do not have a token")
        return ConversationHandler.END

    return await main_menu(update, context)


async def create_wordsets_menu(user_token: str) -> InlineKeyboardMarkup | None:
    wordsets = get_wordsets(API_URL, user_token)
    if not wordsets:
        return None
    buttons = [(ws["title"], ws["id"]) for ws in wordsets]
    return keyboard_in_maker(buttons, "wordsets", 3)


async def show_wordset_menu(context: ContextTypes.DEFAULT_TYPE) -> int:
    user_token = context.user_data.get("user_token", "") if context.user_data else ""
    if not user_token:
        return ConversationHandler.END
    markup = await create_wordsets_menu(user_token)

    if not context.user_data:
        return ConversationHandler.END

    stat_msg_id = context.user_data.get("stat_msg_id")
    quizz_msg_id = context.user_data.get("quizz_msg_id")
    chat_id = context.user_data.get("chat_id")
    logger.debug(f"{stat_msg_id=} :: {quizz_msg_id=} :: {chat_id}")
    if not chat_id:
        return ConversationHandler.END
    if quizz_msg_id:
        context.user_data["quizz_msg_id"] = None
        await context.bot.delete_message(chat_id, quizz_msg_id)
    logger.debug(f"show wordset menu :: {stat_msg_id=}")
    chat_id = context.user_data.get("chat_id")
    msg = "We have some sets for training"
    prev_stats = context.user_data.get("wordset_stats")
    if prev_stats and prev_stats.get("words"):
        msg += f"\nResult\nWords: {prev_stats['words']}"
        msg += f"\nCorrect: {prev_stats['correct']} :: Incorrect: {prev_stats['incorrect']}"

    await context.bot.edit_message_text(
        text=msg, chat_id=chat_id, message_id=stat_msg_id, reply_markup=markup
    )
    return StateEnum.CHOOSING_WORDSET


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.debug("handle main menu :: start")
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    await query.answer()
    if not query.data:
        return ConversationHandler.END

    prefix, next_menu = query.data.split(":")
    logger.debug(f"handle main menu :: conf : {prefix} : {next_menu}")
    logger.debug("handle main menu :: finish")
    return await show_wordset_menu(context)


async def create_wordsets_quizz(user_token: str, set_id: str) -> list | None:
    wordset_quizz = get_wordset_quiz(API_URL, user_token, set_id)
    if not wordset_quizz:
        return None
    return wordset_quizz


async def show_statistics(context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data:
        return None

    stat_msg_id = context.user_data["stat_msg_id"]
    chat_id = context.user_data["chat_id"]
    stats = context.user_data["wordset_stats"]
    msg = "Your statistics:\n"
    msg += f"Words: {stats.get('words')}\n"
    msg += f"Correct {stats.get('correct')}\n"
    msg += f"Incorrect: {stats.get('incorrect')}"
    await context.bot.edit_message_text(msg, chat_id, stat_msg_id)


async def show_wordset_word(context: ContextTypes.DEFAULT_TYPE, play_word) -> int:
    if not context.user_data:
        return ConversationHandler.END

    buttons = [
        (play_word[2].capitalize(), 1),
    ] + [(el.capitalize(), 0) for el in play_word[3]]
    random.shuffle(buttons)
    markup = keyboard_in_maker(buttons, f"wordset>quizz>{play_word[0]}", 2)
    msg = f"{play_word[1].capitalize()}"

    quizz_msg_id = context.user_data.get("quizz_msg_id")
    chat_id = context.user_data.get("chat_id")
    if not chat_id:
        return ConversationHandler.END
    if not quizz_msg_id:
        quizz_msg = await context.bot.send_message(
            chat_id, text=msg, reply_markup=markup
        )
        context.user_data["quizz_msg_id"] = quizz_msg.message_id
    else:
        await context.bot.edit_message_text(
            text=msg, chat_id=chat_id, message_id=quizz_msg_id, reply_markup=markup
        )
    return StateEnum.WORD_PLAY


async def wordset_quizz_play(context: ContextTypes.DEFAULT_TYPE) -> int:
    wordset_quizz = context.user_data["wordset_quizz"] if context.user_data else None
    logger.debug(f"wordset quizz play :: {wordset_quizz}")
    if not wordset_quizz:
        return await show_wordset_menu(context)
    play_word = wordset_quizz.pop()
    if not play_word:
        return await show_wordset_menu(context)
    await show_statistics(context)
    return await show_wordset_word(context, play_word)


async def handle_wordset_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    logger.debug("handle wordset :: start")
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    if not query.data:
        return ConversationHandler.END

    user_token = context.user_data.get("user_token", "") if context.user_data else ""
    prefix, wordset_id = query.data.split(":")
    logger.debug(f"handle main menu :: conf : {prefix} : {wordset_id}")
    wordset_quizz = await create_wordsets_quizz(user_token, wordset_id)
    if not wordset_quizz or not context.user_data:
        return ConversationHandler.END
    context.user_data["wordset_quizz"] = wordset_quizz
    context.user_data["wordset_stats"] = {"words": 0, "correct": 0, "incorrect": 0}
    logger.debug("handle wordset :: finish")
    return await wordset_quizz_play(context)


async def handle_wordset_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("handle wordset play :: start")
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    await query.answer()
    if not query.data:
        return ConversationHandler.END

    prefix, is_correct = query.data.split(":")
    logger.debug(f"handle wordset play :: {prefix} : {is_correct}")
    stats = context.user_data.get("wordset_stats") if context.user_data else None
    if not stats:
        return ConversationHandler.END
    stats["words"] += 1
    if int(is_correct):
        stats["correct"] += 1
    else:
        stats["incorrect"] += 1
    return await wordset_quizz_play(context)


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
    application = Application.builder().token(bot_token).build()

    bot_email = os.getenv("BOT_EMAIL")
    bot_pass = os.getenv("BOT_PASS")
    api_token = get_bot_token(bot_email, bot_pass)
    if not api_token:
        logger.info("bot api token :: empty")
        return None

    application.bot_data["bot_token"] = api_token

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            StateEnum.CHOOSING_ACT: [
                CallbackQueryHandler(handle_main_menu, pattern="main:"),
            ],
            StateEnum.CHOOSING_WORDSET: [
                CallbackQueryHandler(handle_wordset_menu, pattern="wordsets:")
            ],
            StateEnum.WORD_PLAY: [
                CallbackQueryHandler(handle_wordset_play, pattern="wordset>quizz")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
