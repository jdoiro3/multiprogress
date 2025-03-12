import time
import random
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprogress import MultiProcessProgress, progress_bar
from itertools import chain
from rich import print


def do_work(n: int, type: str) -> int:
    sleep_for = random.randint(0, 2)
    for _ in progress_bar(
        range(1, n + 2),
        desc=f"{type}: Sleeping for {sleep_for} secs for each {n} iterations.",
    ):
        time.sleep(sleep_for)
    return n


def demo():
    with ThreadPoolExecutor() as t, ProcessPoolExecutor() as p, MultiProcessProgress():
        p_futures = [p.submit(do_work, i, "process") for i in range(1, 10)]
        t_futures = [t.submit(do_work, i, "thread") for i in range(1, 10)]
        for f in as_completed(chain(p_futures, t_futures)):
            print(f"Done processing {f.result()}")


if __name__ == "__main__":
    demo()
