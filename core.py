from dataclasses import dataclass
import logging
import requests
import random

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


def get_wordset_quiz(api_url: str, api_token: str, set_id: str) -> list | None:
    logger.debug("get wordset quizz :: start")
    url = f"{api_url}/words/quizz/{set_id}"
    headers = {"Authorization": f"Bearer {api_token}"}
    quiz_set = None
    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        quiz_set = res.json()
    except Exception:
        pass
    if not quiz_set:
        return list()
    quizz_words = quiz_set.get("words")
    if not quizz_words:
        return None

    translates = set([tr.get("translate") for tr in quizz_words])
    quizz = []
    for word in quizz_words:
        translate = word["translate"]
        wrong_translates = translates.copy()
        wrong_translates.discard(translate)
        random_translates = random.sample(list(wrong_translates), 3)
        quizz.append((word["id"], word["word"], translate, random_translates))

    logger.debug(f"get wordsets quizz :: {quizz}")
    logger.debug("get wordset quizz :: finish")
    return quizz


def get_word_quiz(word_set: int) -> WordQuizz:
    return WordQuizz(
        word="approve", variants=("пара", "непара", "одобрить"), correct="одобрить"
    )
