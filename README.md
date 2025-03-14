# Multiprogress

A simple to use `progress_bar` in sub-processes or threads using [rich](https://github.com/Textualize/rich).
See the [examples](./src/multiprogress/examples) folder for more examples.

## Demo Video

[![demo](https://asciinema.org/a/85R4jTtjKVRIYXTcKCNq0vzYH.svg)](https://asciinema.org/a/FtueDHOSfvf4J30JNdPQnGNHg?autoplay=1)

## Examples

### Simple

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

### Using Other Rich Features

> [!Note]
> The `progress_bar` doesn't need to know about the `MultiProgress` instance.
> The only time the two components will need to be aware of one another is the case
> of multiple instances of `MultiProgress` being used in the main process. In such cases
> you will use a `key` (a `string`) to send progress updates to the correct instance.

```python
import time
import random
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprogress import MultiProgress, progress_bar
from itertools import chain
from rich import print
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Group
from rich.live import Live


def do_work(n: int, key: str) -> int:
    sleep_for = random.randint(0, 2)
    for _ in progress_bar(
        range(1, n + 2),
        desc=f"Sleeping for {sleep_for} secs for each {n} iterations.",
        key=key, # Used to specify which MultiProgress this will report to
    ):
        time.sleep(sleep_for)
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
```
