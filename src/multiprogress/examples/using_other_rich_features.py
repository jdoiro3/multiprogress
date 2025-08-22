import time
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprogress import MultiProgress, progress_bar
import random


def work(status_name: str) -> str:
    for _ in progress_bar(
        range(random.randint(2, 40)),
        desc=f"Working on task for {status_name}",
        metrics_func=lambda: dict(name="Joe"),
    ):
        time.sleep(random.random() * 2)
    return status_name


def demo():
    console = Console()
    status = console.status("Working on tasks...")
    with (
        ProcessPoolExecutor() as p,
        MultiProgress(transient=True)(live_mode=False) as mp,
        Live(Panel(Group(status, mp))),
    ):
        futures = [
            p.submit(work, status_name)
            for status_name in ("status1", "status2", "status3")
        ]
        done = []
        for f in as_completed(futures):
            done.append(f.result())
            status.update(f"[bold green]Done tasks: {','.join(done)}")
        status.update("[bold green]All are done!!!")


if __name__ == "__main__":
    demo()
