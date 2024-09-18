import os
from dataclasses import dataclass
import logging
import requests
import random
from time import sleep

from dotenv import load_dotenv

from common import random_email, random_lower_string

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


API_URL = os.getenv("API_URL", "")


@dataclass
class WordQuizz:
    word: str
    variants: tuple[str, ...]
    correct: str


def get_query(url: str, api_token: str, params: dict = None) -> list | dict | None:
    url = f"{API_URL}{url}"
    headers = {"Authorization": f"Bearer {api_token}"}
    logger.debug(f"get_query :: {url} :: {params}")
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching post: {response.json()}")
        logger.error(f"Error fetching get: {e}")


def post_query(url: str, api_token: str | None,
               data: dict | None = None, json_data: dict | None = None) -> list | dict | None:
    url = f"{API_URL}{url}"
    headers = {}
    if api_token:
        headers = {"Authorization": f"Bearer {api_token}"}
    logger.debug(f"post_query :: {url} :: {data} :: {json_data}")
    try:
        response = requests.post(url, headers=headers, data=data, json=json_data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching post: {e}")


def get_bot_token(bot_email, bot_pass):
    """Get bot token for the api"""
    logger.debug("bot api token :: start")
    api_token = ""
    while not api_token:
        url = "/login/access-token"
        data = {"username": bot_email, "password": bot_pass}
        result = post_query(url, None, data)
        if not result:
            sleep(2)
            continue
        bot_token = result.get("access_token")
        return bot_token


async def get_user_token(user_id: int, bot_token: str) -> str | None:
    logger.debug("user api token :: start")
    url = f"/login/access-token-bot"
    data = {"tg_id": user_id}
    result = post_query(url, bot_token, json_data=data)

    logger.debug("user api token :: finish")
    if result:
        user_token = result.get("access_token")
        return user_token


async def reg_user(user_id: int, bot_token: str) -> str | None:
    logger.debug("user reg :: start")

    url = f"/users/"
    data = {
        "email": random_email(),
        "tg_id": user_id,
        "password": random_lower_string(),
    }

    result = post_query(url, bot_token, json_data=data)
    if result:
        user_token = result.get("access_token")
        return user_token


def get_wordsets(api_token: str, page: int = 1, size: int = 6) -> dict:
    """Fetch word sets from the API."""
    logger.debug("get_wordsets :: start")
    params = {"page": page, "size": size}
    url = f"/words/sets/"
    wordsets = get_query(url, api_token, params)

    logger.debug(f"get_wordsets :: {wordsets}")
    logger.debug("get_wordsets :: finish")
    return wordsets


def get_wordset_quiz(api_token: str, set_id: str) -> list | None:
    logger.debug("get wordset quizz :: start")

    url = f"/words/sets/{set_id}/quizz/"
    quiz_set = get_query(url, api_token)

    if not quiz_set:
        return None

    quizz_words = quiz_set.get("words")
    if not quizz_words:
        return None

    logger.debug(f"get wordsets quizz :: {quizz_words}")
    logger.debug("get wordset quizz :: finish")
    return quizz_words
