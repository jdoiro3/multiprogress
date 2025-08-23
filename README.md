# Multiprogress

A simple to use `progress_bar` in sub-processes or threads using [rich](https://github.com/Textualize/rich).
See the [examples](./src/multiprogress/examples) folder for more examples.

```python
import time
import random
from concurrent.futures import ProcessPoolExecutor
from multiprogress import MultiProgress, progress_bar


def do_work(n: int) -> int:
    sleep_for = random.randint(0, 2)
    for _ in progress_bar(
        range(1, n + 2), desc=f"Sleeping for {sleep_for} secs for each {n} iterations."
    ):
        time.sleep(sleep_for)
    return sleep_for


def demo():
    with ProcessPoolExecutor() as p, MultiProgress():
        print(list(p.map(do_work, range(10))))
```

## Install

```
pip install multiprog
```

### Using Other Rich Features

> [!Note]
> The `progress_bar` function doesn't need to know about the `MultiProgress` instance.
> The only time the two components will need to share state is the case
> where multiple instances of `MultiProgress` are being used in the main process. In such cases
> you will use a `key` to send progress updates to the correct instance.

```python
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
```

[![asciicast](https://asciinema.org/a/655OZvrGusWRldzpHGjhOjhOD.svg)](https://asciinema.org/a/655OZvrGusWRldzpHGjhOjhOD)
