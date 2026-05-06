import random
import time


def random_delay(lo: float = 2.0, hi: float = 5.0) -> None:
    time.sleep(random.uniform(lo, hi))


def is_blocked(source: str) -> bool:
    src = source.lower()
    return any(
        k in src
        for k in [
            "robot check",
            "captcha",
            "enter the characters you see below",
            "sorry, we just need to make sure",
            "automated access",
        ]
    )
