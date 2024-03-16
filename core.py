from dataclasses import dataclass
import logging
import requests

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")


@dataclass
class WordQuizz:
    word: str
    variants: tuple[str, ...]
    correct: str


def get_wordsets(api_url: str, api_token: str) -> list:
    logger.debug("get wordsets :: start")
    url = f"{api_url}/words/sets/"
    headers = {"Authorization": f"Bearer {api_token}"}
    wordsets = None
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        wordsets = res.json()
    except Exception:
        pass

    logger.debug(f"get wordsets :: {wordsets}")
    logger.debug("get wordsets :: finish")
    return wordsets


def get_word_quiz(word_set: int) -> WordQuizz:
    return WordQuizz(
        word="approve", variants=("пара", "непара", "одобрить"), correct="одобрить"
    )
