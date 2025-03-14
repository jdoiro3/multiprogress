import os
import threading
from dataclasses import dataclass
from multiprocessing.connection import Connection, Listener, Client
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
    Final,
)
import tempfile
from pathlib import Path
import pickle

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
import atexit

DONE: Final = "DONE"
HELLO: Final = "HELLO"
LOCALHOST: Final = "localhost"
PORT: Final = 6000
AUTH_KEY: Final = b"progress-bar-secret-key"

PROGRESS_KEYS_TO_PORTS_FILE = (
    Path(tempfile.gettempdir()) / "progress_keys_to_ports.pickle"
)
if not PROGRESS_KEYS_TO_PORTS_FILE.exists():
    with open(PROGRESS_KEYS_TO_PORTS_FILE, "wb+") as f:
        pickle.dump({}, f)
    atexit.register(PROGRESS_KEYS_TO_PORTS_FILE.unlink)


class ProgressInitializationError(Exception):
    pass


def join(items, sep):
    r = [sep] * (len(items) * 2 - 1)
    r[0::2] = items
    return r


def persist_key_to_port(key: str, port: int) -> None:
    with open(PROGRESS_KEYS_TO_PORTS_FILE, "rb") as f:
        keys_to_ports: dict = pickle.load(f)
    if key in keys_to_ports:
        raise ValueError(
            f"{key} is not a unique progress key. Current keys are: {keys_to_ports.keys()}."
        )
    keys_to_ports[key] = port
    with open(PROGRESS_KEYS_TO_PORTS_FILE, "wb") as f:
        pickle.dump(keys_to_ports, f)


def get_port(key: str) -> int:
    with open(PROGRESS_KEYS_TO_PORTS_FILE, "rb") as f:
        keys_to_ports: dict = pickle.load(f)
    return keys_to_ports[key]


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

    _PORT = PORT
    _FIRST_INSTANCE = True

    def __init__(
        self,
        *args,
        refresh_every_n_secs: Optional[float] = None,
        live_mode: bool = True,
        key: str = "main",
        **kwargs,
    ):
        if not self.__class__._FIRST_INSTANCE:
            self.__class__._PORT += 1
        self.__class__._FIRST_INSTANCE = False
        persist_key_to_port(key, self.__class__._PORT)
        self.PORT = self.__class__._PORT
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
        self._live = live_mode

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
        if self._live:
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
            listener = Listener((LOCALHOST, self.PORT), authkey=AUTH_KEY, backlog=1000)
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
        with Client((LOCALHOST, self.PORT), authkey=AUTH_KEY) as conn:
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
    key: str = "main",
):
    """
    Used within a MultiProcessProgress context to report progress of an iterable to the parent (or same) process.
    """
    if not id:
        id = str(threading.get_ident())
    with Client((LOCALHOST, get_port(key)), authkey=AUTH_KEY) as conn:
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
                    pid=os.getpid(),
                    id=id,
                    metrics=metrics_func(),
                    completed=i + 1,
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
