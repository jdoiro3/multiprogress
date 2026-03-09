import time
from rich.progress import TextColumn, SpinnerColumn
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from concurrent.futures import ProcessPoolExecutor, as_completed
from enriched_progress import MultiProgress, add_task
import random
from rich.columns import Columns


stages = [
    "[bold grey]Initializing[/]",
    "[bold magenta]Downloading[/]",
    "[bold blue]Processing[/]",
    "[bold green]Finalizing[/]",
]


def work(status_name: str) -> str:
    with add_task(
        f"Working on task for {status_name}", total=1, stage="Starting"
    ) as update:
        for stage in stages:
            time.sleep(random.random() * 10)
            update(stage=stage)
        update(stage="[bold green]Completed", completed=1)
    return status_name


def demo() -> None:
    console = Console()
    status = console.status("Working on tasks...")
    with (
        ProcessPoolExecutor() as p,
        MultiProgress(
            SpinnerColumn(finished_text="✅"),
            TextColumn("{task.description} ({task.fields[stage]})", justify="right"),
        )(live_mode=False) as mp,
        Live(
            Panel(
                Columns(
                    [
                        Panel(Group(status, mp), title="Tasks", style="bold white"),
                        Panel("CPU: 24%", title="Processor", style="bold green"),
                        Panel("RAM: 13%", title="Memory", style="bold magenta"),
                        Panel("Disk: 10%", title="Storage", style="bold red"),
                    ]
                ),
                title="Job 123",
                style="bold white",
            )
        ),
    ):
        futures = [
            p.submit(work, status_name)
            for status_name in ("status1", "status2", "status3")
        ]
        done: list[str] = []
        for f in as_completed(futures):
            done.append(f.result())
            status.update(f"[bold green]Done tasks: {','.join(done)}")
        status.update("[bold green]All are done!!!")


if __name__ == "__main__":
    demo()
