import logging
import os
import random
from enum import IntEnum, auto

from telegram import (
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)
from dotenv import load_dotenv

from common import keyboard_in_maker, UserInfo, set_context_data, get_context_data, \
    create_menu_markup, BotInfo, split_query, QuizzTypeEnum, main_bot_menu, BotMenu
from core import get_wordsets, get_wordset_quiz, get_bot_token, get_user_token, reg_user
from data.messages import bot_messages

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


class StateEnum(IntEnum):
    CHOOSING_ACT = auto()
    CHOOSING_WORDSET = auto()
    WORD_PLAY = auto()


async def clear_messages(context: ContextTypes.DEFAULT_TYPE):
    if not context or not context.user_data:
        return None
    user_info = get_context_data(context.user_data, UserInfo)
    chat_id = user_info.chat_id
    messages = user_info.msg_to_delete
    if not chat_id or not messages:
        return None
    for msg_id in messages:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except Exception:
            pass
    user_info.msg_to_delete = []


def is_context_correct(update: Update | None, context: ContextTypes.DEFAULT_TYPE | None,
                       need_message: bool = True, need_user_data: bool = True,
                       need_query: bool = False) -> bool:
    if need_message and not (update.message and update.message.from_user):
        return False
    if not context:
        return False
    if need_user_data and not context.user_data:
        return False
    if need_query and not update.callback_query:
        return False
    return True


async def set_state(context: ContextTypes.DEFAULT_TYPE, state: int) -> int:
    await clear_messages(context)
    return state


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send first question for the user"""
    if not is_context_correct(update, context):
        return ConversationHandler.END

    text = main_bot_menu.msg
    markup = create_menu_markup(main_bot_menu)
    new_message = await update.message.reply_text(
        text,
        reply_markup=markup,
    )
    bot_info = BotInfo(active_bot_msg=new_message.message_id)
    set_context_data(context.user_data, bot_info)

    return await set_state(context, StateEnum.CHOOSING_ACT)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask user for input."""
    if not is_context_correct(update, context, need_user_data=False):
        return ConversationHandler.END

    user_id = update.message.from_user.id

    bot_token = context.bot_data.get("bot_token")
    user_token = await get_user_token(user_id, bot_token)
    if not user_token:
        user_token = await reg_user(user_id, bot_token)

    user_info = UserInfo(user_id=user_id, chat_id=update.message.chat_id, user_token=user_token,
                         msg_to_delete=[update.message.message_id,])
    logger.debug(f"{user_info=}")
    set_context_data(context.user_data, user_info)
    return await show_main_menu(update, context)


def create_wordsets_menu(user_token: str, page: int = 1) -> BotMenu | None:
    wordsets = get_wordsets(user_token, page)
    if not wordsets:
        return None

    wordsets_pack = [(str(idx + 1), ws["title"]) for idx, ws in enumerate(wordsets["items"])]
    menu_text = bot_messages.get("wordsets")
    menu_text += "\n".join([f"{idx}. {title}" for idx, title in wordsets_pack])

    prev_page, next_page = page != 1, page != wordsets["pages"]
    buttons = [(ws[0], ws[1]) for ws in wordsets_pack]
    if prev_page:
        buttons.append(("<<", f"page_{page - 1}"))
    if next_page:
        buttons.append((">>", f"page_{page + 1}"))
    return BotMenu(msg=menu_text, prefix="wordsets", buttons=buttons, number=3)


async def show_wordset_menu(context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_context_correct(context=context, update=None, need_query=False, need_message=False):
        return ConversationHandler.END

    user_info = get_context_data(context.user_data, UserInfo)
    bot_info = get_context_data(context.user_data, BotInfo)

    wordsets_menu = create_wordsets_menu(user_info.user_token)
    markup = create_menu_markup(wordsets_menu)
    await context.bot.edit_message_text(
        text=wordsets_menu.msg, chat_id=user_info.chat_id, message_id=bot_info.active_bot_msg, reply_markup=markup
    )
    return StateEnum.CHOOSING_WORDSET


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.debug("handle main menu :: start")
    if not is_context_correct(update, context, need_message=False, need_query=True):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    bot_info = get_context_data(context.user_data, BotInfo)
    prefix, choice = split_query(query.data)
    logger.debug(f"handle main menu :: {prefix=} : {choice=}")

    logger.debug("handle main menu :: finish")
    if choice == "words":
        bot_info.quizz_type = QuizzTypeEnum.WORDS
        return await show_wordset_menu(context)

    return ConversationHandler.END


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
                CallbackQueryHandler(handle_main_menu, pattern=main_bot_menu.prefix)
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
