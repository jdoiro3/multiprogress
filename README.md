# Multiprogress

A simple to use `progress_bar` in sub-processes using [rich](https://github.com/Textualize/rich).

```python
import time
import random
from concurrent.futures import ProcessPoolExecutor
from multiprogress import MultiProcessProgress, progress_bar

def do_work(n: int) -> int:
    sleep_for = random.randint(0, 2)
    for _ in progress_bar(
        range(1, n + 2), desc=f"Sleeping for {sleep_for} secs for each {n} iterations."
    ):
        time.sleep(sleep_for)
    return sleep_for


def demo():
    with ProcessPoolExecutor() as p, MultiProcessProgress():
        print(list(p.map(do_work, range(10))))
```
