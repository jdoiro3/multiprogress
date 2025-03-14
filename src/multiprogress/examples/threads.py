import time
import random
from concurrent.futures import ThreadPoolExecutor
from multiprogress import MultiProgress, progress_bar


def do_work(n: int) -> int:
    sleep_for = random.randint(0, 2)
    for _ in progress_bar(
        range(1, n + 2), desc=f"Sleeping for {sleep_for} secs for each {n} iterations."
    ):
        time.sleep(sleep_for)
    return sleep_for


def demo():
    with ThreadPoolExecutor() as t, MultiProgress():
        print(list(t.map(do_work, range(10))))


if __name__ == "__main__":
    demo()
