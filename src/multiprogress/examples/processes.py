import time
import random
from concurrent.futures import ProcessPoolExecutor
from multiprogress import MultiProgress, progress_bar
import os
from functools import lru_cache
import random


@lru_cache
def pid() -> int:
    return os.getpid()


def do_work(n: int) -> int:
    sleep_for = random.randint(0, 2)
    color = random.randint(0, 255)
    for _ in progress_bar(
        list(range(1, n + 2)),
        desc=f"Sleeping for {sleep_for} secs for each {n} iterations.",
        metrics_func=lambda: dict(pid=f"[color({color})]{pid()}"),
    ):
        time.sleep(sleep_for)
    return sleep_for


def demo():
    with ProcessPoolExecutor() as p, MultiProgress():
        print(list(p.map(do_work, range(10))))


if __name__ == "__main__":
    demo()
