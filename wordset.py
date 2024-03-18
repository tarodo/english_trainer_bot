from enum import StrEnum
from dataclasses import dataclass, asdict


@dataclass
class WordsetAttempt:
    word: str
    correct: str
    attempt: str


@dataclass
class Wordset:
    stat_msg_id: int | None
    quizz_msg_id: int | None
    words_cnt: int
    correct_cnt: int
    incorrect_cnt: int
    attempts: list[WordsetAttempt] | None


QUERY_MAIN_PREFIX = "wordsets"
QUERY_QUIZZ_PREFIX = f"{QUERY_MAIN_PREFIX}>quizz>{{word_id}}"


class MsgEnum(StrEnum):
    WORDSET_CHOOSE = "Choose a wordset for the quizz"
    STATISTIC_SHOW = (
        "Words: {words_cnt} | Correct: {correct_cnt} | Incorrect: {incorrect_cnt}"
    )


my_wordset = Wordset(1, 2, 10, 8, 2, [WordsetAttempt("hello", "привет", "выоаыв")])
print(MsgEnum.STATISTIC_SHOW.format(**asdict(my_wordset)))
