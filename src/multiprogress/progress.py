import os
import random
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing.connection import Connection, Listener, Client, wait
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    Final,
)

from rich.console import RenderableType
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    ProgressColumn,
)

DONE: Final = "DONE"
HELLO: Final = "HELLO"


class ProgressInitializationError(Exception):
    pass


def join(items, sep):
    r = [sep] * (len(items) * 2 - 1)
    r[0::2] = items
    return r


@dataclass
class AddTaskMessage:
    desc: str
    metrics: Dict[str, Any]
    total: float
    pid: int
    id: str


@dataclass
class ProgressUpdateMessage:
    pid: int
    metrics: Dict[str, Any]
    completed: int
    id: str


class MultiProcessProgress(Progress):
    """
    An extended rich.Progress that can report progress of forked sub-processes. The
    process reporting progress can also be the same process.

    Example:

    ```python
    from .progress_bar import MultiProcessProgress, progress_bar
    import multiprocessing as mp
    import time

    def foo(x):
        for _ in progress_bar(range(x), desc=f"Iterating {x} times..."):
            time.sleep(.1)

    with futures.ProcessPoolExecutor() as p, MultiProcessProgress():
        p.map(foo, (50, 100, 500))
    ```

    """

    def __init__(self, *args, refresh_every_n_secs: Optional[float] = None, **kwargs):
        super().__init__(
            TextColumn("{task.description} {task.percentage:>3.0f}%"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            *args,
            **kwargs,
            refresh_per_second=1 / refresh_every_n_secs if refresh_every_n_secs else 10,
        )
        self._initial_columns: Collection[Union[str, ProgressColumn]] = self.columns

    def get_renderables(self) -> Iterable[RenderableType]:
        for task in self.tasks:
            self.columns = (
                *self._initial_columns,
                TextColumn("•"),
                *join(
                    [
                        TextColumn(f"{v} {k}")
                        for k, v in sorted(
                            task.fields.items(), key=lambda item: item[0]
                        )
                    ],
                    TextColumn("•"),
                ),
            )
            yield self.make_tasks_table([task])

    def __enter__(self):
        self._id_to_task_id: Dict[Tuple[int, str], TaskID] = {}
        self._ids: List[str] = []
        super().__enter__()

        def handle_client(conn: Connection):
            while True:
                try:
                    msg: Optional[
                        Union[AddTaskMessage, ProgressUpdateMessage]
                    ] = conn.recv()
                    if isinstance(msg, AddTaskMessage):
                        task_id = self.add_task(
                            description=msg.desc, total=msg.total, **msg.metrics
                        )
                        if msg.id in self._ids:
                            raise ProgressInitializationError(
                                f"Progress ids must be unique. {msg.id} already in {self._ids}."
                            )
                        self._id_to_task_id[(msg.pid, msg.id)] = task_id
                    elif isinstance(msg, ProgressUpdateMessage):
                        self.update(
                            self._id_to_task_id[(msg.pid, msg.id)],
                            completed=msg.completed,
                            **msg.metrics,
                        )
                except EOFError:
                    break

        def server():
            listener = Listener(
                ("localhost", 6000), authkey=b"secret password", backlog=50
            )
            while True:
                conn = listener.accept()  # this will block forever
                msg = conn.recv()
                if msg == DONE:
                    listener.close()
                    break
                client_thread = threading.Thread(
                    target=handle_client, args=(conn,), daemon=True
                )
                client_thread.start()

        self._server = threading.Thread(
            target=server, daemon=True
        )  # daemon so thread stops whenever main thread stops
        self._server.start()
        return self

    def __exit__(self, *args, **kwargs):
        super().__exit__(*args, **kwargs)
        with Client(("localhost", 6000), authkey=b"secret password") as conn:
            conn.send(DONE)
        self._server.join()


def empty() -> Dict[str, Any]:
    return {}


def progress_bar(
    iterable: Any,
    desc: str,
    total: int | None = None,
    metrics_func: Callable[[], Dict[str, Any]] = empty,
    id: str = "",
):
    """
    Used within a MultiProcessProgress context to report progress of an iterable to the parent (or same) process.
    """
    with Client(("localhost", 6000), authkey=b"secret password") as conn:
        conn.send(HELLO)
        conn.send(
            AddTaskMessage(
                desc=desc,
                metrics=metrics_func(),
                total=total or len(iterable),
                pid=os.getpid(),
                id=id,
            )
        )
        for i, r in enumerate(iterable):
            conn.send(
                ProgressUpdateMessage(
                    pid=os.getpid(), id=id, metrics=metrics_func(), completed=i + 1
                )
            )
            yield r
        conn.send(
            ProgressUpdateMessage(
                pid=os.getpid(),
                id=id,
                metrics=metrics_func(),
                completed=total or len(iterable),
            )
        )


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


if __name__ == "__main__":
    demo()
