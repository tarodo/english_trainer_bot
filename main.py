import logging
import os
import random
from enum import IntEnum, auto

from telegram import (
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


PAGE_PREFIX = "page_"


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

    wordsets_pack = [(str(idx + 1), ws["title"], ws["id"]) for idx, ws in enumerate(wordsets["items"])]
    logger.debug(f"{wordsets_pack=}")
    menu_text = bot_messages.get("wordsets")
    menu_text += "\n".join([f"{idx}. {title}" for idx, title, _ in wordsets_pack])

    prev_page, next_page = page != 1, page != wordsets["pages"]
    buttons = [(ws[0], ws[2]) for ws in wordsets_pack]
    if prev_page:
        buttons.append(("<<", f"{PAGE_PREFIX}{page - 1}"))
    if next_page:
        buttons.append((">>", f"{PAGE_PREFIX}{page + 1}"))
    logger.debug(f"{buttons=}")
    return BotMenu(msg=menu_text, prefix="wordsets", buttons=buttons, number=3)


async def show_wordsets_menu(context: ContextTypes.DEFAULT_TYPE, page: int = 1) -> int:
    if not is_context_correct(context=context, update=None, need_query=False, need_message=False):
        return ConversationHandler.END

    user_info = get_context_data(context.user_data, UserInfo)
    bot_info = get_context_data(context.user_data, BotInfo)

    wordsets_menu = create_wordsets_menu(user_info.user_token, page)
    markup = create_menu_markup(wordsets_menu)
    await context.bot.edit_message_text(
        text=wordsets_menu.msg, chat_id=user_info.chat_id, message_id=bot_info.active_bot_msg, reply_markup=markup
    )
    return StateEnum.CHOOSING_WORDSET


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_context_correct(update, context, need_message=False, need_query=True):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    bot_info = get_context_data(context.user_data, BotInfo)
    prefix, choice = split_query(query.data)
    logger.debug(f"handle main menu :: {prefix=} : {choice=}")

    if choice == QuizzTypeEnum.WORDSETS.value:
        bot_info.quizz_type = QuizzTypeEnum.WORDSETS
        return await show_wordsets_menu(context)

    return ConversationHandler.END


async def show_statistics(context: ContextTypes.DEFAULT_TYPE):
    bot_info = get_context_data(context.user_data, BotInfo)
    user_info = get_context_data(context.user_data, UserInfo)

    stat_data = bot_info.stat_data
    ready_cnt = stat_data.get('correct') + stat_data.get('incorrect')
    msg = "Промежуточный результат:\n"
    msg += f"Слов: {ready_cnt} / {stat_data.get('words')}\n"
    msg += f"Верно {stat_data.get('correct')}\n"
    msg += f"Ошибки: {stat_data.get('incorrect')}"
    await context.bot.edit_message_text(msg, user_info.chat_id, bot_info.statistic_msg)


async def show_wordset_word(context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_info = get_context_data(context.user_data, BotInfo)
    user_info = get_context_data(context.user_data, UserInfo)

    play_word = bot_info.quizz_active_data
    buttons = [
        (play_word["translate"].capitalize(), 1),
    ] + [(el["translate"].capitalize(), 0) for el in play_word["wrong_words"]]
    random.shuffle(buttons)
    markup = keyboard_in_maker(buttons, f"wordset>quizz>{play_word['id']}", 2)
    msg = f"{play_word['word'].capitalize()}"

    if not bot_info.active_bot_msg:
        quizz_msg = await context.bot.send_message(
            user_info.chat_id, text=msg, reply_markup=markup
        )
        bot_info.active_bot_msg = quizz_msg.message_id
    else:
        await context.bot.edit_message_text(
            text=msg, chat_id=user_info.chat_id, message_id=bot_info.active_bot_msg, reply_markup=markup
        )
    return StateEnum.WORD_PLAY


async def show_result(context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_info = get_context_data(context.user_data, BotInfo)
    user_info = get_context_data(context.user_data, UserInfo)

    stat_data = bot_info.stat_data
    ready_cnt = stat_data.get('correct') + stat_data.get('incorrect')
    msg = "Итог игры: \n"
    msg += f"Слов: {ready_cnt} / {stat_data.get('words')}\n"
    msg += f"Верно {stat_data.get('correct')}\n"
    msg += f"Ошибки: {stat_data.get('incorrect')}"

    end_menu = BotMenu(msg, QuizzTypeEnum.WORDSETS_WORD.value, [("Еще", QuizzTypeEnum.WORDSETS.value)])
    markup = create_menu_markup(end_menu)
    user_info.msg_to_delete.append(bot_info.active_bot_msg)
    bot_info.active_bot_msg = None
    bot_info.active_bot_msg = bot_info.statistic_msg
    bot_info.statistic_msg = None
    await context.bot.edit_message_text(
        text=msg, chat_id=user_info.chat_id, message_id=bot_info.active_bot_msg, reply_markup=markup
    )

    return await set_state(context, StateEnum.WORD_PLAY)


async def wordset_quizz_play(context: ContextTypes.DEFAULT_TYPE) -> int:
    bot_info = get_context_data(context.user_data, BotInfo)
    quizz_data = bot_info.quizz_data

    if not quizz_data:
        return await show_result(context)
    play_word = quizz_data.pop()

    if not bot_info.statistic_msg:
        bot_info.statistic_msg = bot_info.active_bot_msg
        bot_info.active_bot_msg = None
    bot_info.quizz_active_data = play_word

    await show_statistics(context)
    return await show_wordset_word(context)


async def handle_wordset_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    logger.debug("handle wordset :: start")
    if not is_context_correct(update, context, need_message=False, need_query=True):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    prefix, wordset_id = split_query(query.data)
    logger.debug(f"handle wordset menu :: {prefix=} : {wordset_id=}")

    if wordset_id.startswith(PAGE_PREFIX):
        page = int(wordset_id.split("_")[1])
        logger.debug(f"handle wordset menu :: {page=}")
        return await show_wordsets_menu(context, page)

    user_info = get_context_data(context.user_data, UserInfo)
    bot_info = get_context_data(context.user_data, BotInfo)
    wordset_quizz = get_wordset_quiz(user_info.user_token, wordset_id)

    bot_info.quizz_data = wordset_quizz
    bot_info.stat_data = {"words": len(wordset_quizz), "correct": 0, "incorrect": 0}

    logger.debug("handle wordset :: finish")
    return await wordset_quizz_play(context)


async def handle_wordset_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug("handle wordset play :: start")
    if not is_context_correct(update, context, need_message=False, need_query=True):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    prefix, is_correct = split_query(query.data)
    if is_correct == QuizzTypeEnum.WORDSETS.value:
        return await handle_main_menu(update, context)

    logger.debug(f"handle wordset play :: {prefix=} : {is_correct=}")
    user_info = get_context_data(context.user_data, UserInfo)
    bot_info = get_context_data(context.user_data, BotInfo)

    stats = bot_info.stat_data
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
                CallbackQueryHandler(handle_wordset_menu, pattern=QuizzTypeEnum.WORDSETS.value)
            ],
            StateEnum.WORD_PLAY: [
                CallbackQueryHandler(handle_wordset_play, pattern=QuizzTypeEnum.WORDSETS_WORD.value)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
