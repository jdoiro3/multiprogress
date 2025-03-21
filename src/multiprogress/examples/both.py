import time
import random
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprogress import MultiProgress, progress_bar
from itertools import chain
from rich import print
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
import os


def do_work(n: int, key: str) -> int:
    sleep_for = random.random()
    pid = os.getpid()
    for _ in progress_bar(
        range(1, n + 2),
        desc=f"Sleeping for {sleep_for:.2f} secs for each {n} iterations.",
        key=key,
        metrics_func=lambda: {"pid": f"[color({pid % 250})]{pid}"},
    ):
        time.sleep(1 * sleep_for)
    return n


def demo():
    progress_p = MultiProgress(key="process", live_mode=False, transient=True)
    progress_t = MultiProgress(key="thread", live_mode=False, transient=True)
    layout = Layout()
    layout.split_column(
        Layout(Panel(progress_p, title="processes"), name="top"),
        Layout(Panel(progress_t, title="threads"), name="bottom"),
    )
    with ThreadPoolExecutor() as t, ProcessPoolExecutor() as p, progress_p, progress_t, Live(
        layout
    ):
        p_futures = [p.submit(do_work, i, "process") for i in range(1, 10)]
        t_futures = [t.submit(do_work, i, "thread") for i in range(1, 10)]
        for f in as_completed(chain(p_futures, t_futures)):
            print(f"Done processing {f.result()}")


if __name__ == "__main__":
    demo()
