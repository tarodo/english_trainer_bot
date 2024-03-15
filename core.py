from dataclasses import dataclass


@dataclass
class WordQuizz:
    word: str
    variants: tuple[str, ...]
    correct: str


def get_word_quiz(word_set: int) -> WordQuizz:
    return WordQuizz(
        word="approve", variants=("пара", "непара", "одобрить"), correct="одобрить"
    )
