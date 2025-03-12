# Multiprogress

A simple to use `progress_bar` in sub-processes or threads using [rich](https://github.com/Textualize/rich). 
See the [examples](./src/multiprogress/examples) folder for more examples.

[![asciinema CLI
demo]([[https://asciinema.org/a/85R4jTtjKVRIYXTcKCNq0vzYH.svg](https://asciinema.org/a/FtueDHOSfvf4J30JNdPQnGNHg](https://asciinema.org/a/85R4jTtjKVRIYXTcKCNq0vzYH.svg)))]([https://asciinema.org/a/85R4jTtjKVRIYXTcKCNq0vzYH](https://asciinema.org/a/FtueDHOSfvf4J30JNdPQnGNHg)?autoplay=1)

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
