import os
import threading
from dataclasses import dataclass
from multiprocessing.connection import Connection, Listener, Client
from collections.abc import Sized
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
    TypeVar,
    Type,
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
from contextlib import contextmanager

DONE: Final = "DONE"
HELLO: Final = "HELLO"
LOCALHOST: Final = "localhost"
PORT: Final = 6000
AUTH_KEY: Final = b"progress-bar-secret-key"

T = TypeVar("T")

PROGRESS_KEYS_TO_PORTS_FILE = (
    Path(tempfile.gettempdir()) / "progress_keys_to_ports.pickle"
)
if not PROGRESS_KEYS_TO_PORTS_FILE.exists():
    with open(PROGRESS_KEYS_TO_PORTS_FILE, "wb+") as f:
        pickle.dump({}, f)
    atexit.register(PROGRESS_KEYS_TO_PORTS_FILE.unlink)


class ProgressInitializationError(Exception):
    pass


def join(items: List[T], sep: T) -> List[T]:
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


def remove_key(key: str) -> None:
    with open(PROGRESS_KEYS_TO_PORTS_FILE, "rb") as f:
        keys_to_ports: dict = pickle.load(f)
    if key not in keys_to_ports:
        raise ValueError(f"{key} is not a key in: {keys_to_ports.keys()}.")
    keys_to_ports.pop(key)
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
    total: float | None
    pid: int
    id: str


@dataclass
class ProgressUpdateMessage:
    id: str
    pid: int
    metrics: Dict[str, Any]
    completed: float | None = None
    advance: float | None = None
    desc: str | None = None
    visible: bool = True
    refresh: bool = False


class MultiProgress(Progress):
    """
    An extended rich.Progress that can report progress of forked sub-processes. The
    process reporting progress can also be the same process.

    Example:

    ```python
    from .progress_bar import MultiProgress, progress_bar
    import multiprocessing as mp
    import time

    def foo(x):
        for _ in progress_bar(range(x), desc=f"Iterating {x} times..."):
            time.sleep(.1)

    with futures.ProcessPoolExecutor() as p, MultiProgress():
        p.map(foo, (50, 100, 500))
    ```

    """

    _PORT = PORT
    _FIRST_INSTANCE = True

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

    def __new__(cls, *args, **kwargs) -> "MultiProgress":
        if not cls._FIRST_INSTANCE:
            cls._PORT += 1
        cls._FIRST_INSTANCE = False

        self = super().__new__(cls)
        self._called = False
        self.live_mode = True
        self._key = "main"
        self._port = cls._PORT

        return self

    def __call__(self, key: str = "main", live_mode: bool = True) -> "MultiProgress":
        self._called = True
        self._key = key
        self.live_mode = live_mode
        persist_key_to_port(self._key, self._port)
        return self

    def __enter__(self) -> "MultiProgress":
        self._id_to_task_id: Dict[Tuple[int, str], TaskID] = {}
        self._ids: List[str] = []
        self._initial_columns: tuple[str | ProgressColumn, ...] = self.columns

        if not self._called:
            self.__call__()

        if self.live_mode:
            super().__enter__()

        def handle_client(conn: Connection):
            """Progress client handler."""
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
                            advance=msg.advance,
                            **msg.metrics,
                        )
                except EOFError:
                    break

        def server():
            """The server that handles creating the listener and creating progress client handlers."""
            listener = Listener((LOCALHOST, self._port), authkey=AUTH_KEY, backlog=1000)
            while True:
                conn = listener.accept()
                # ^ This will block forever
                hello_or_done = conn.recv()
                # ^ Each progress client will first send the hello message. Only one client (the parent)
                # process will send the done message, signaling all progress clients are done.
                if hello_or_done == DONE:
                    listener.close()
                    break
                client_thread = threading.Thread(
                    target=handle_client, args=(conn,), daemon=True
                )
                client_thread.start()
                # ^ Each thread handles only one progress client

        self._server = threading.Thread(
            target=server, daemon=True
        )  # daemon so thread stops whenever main thread stops
        self._server.start()
        return self

    def __exit__(self, *args, **kwargs) -> None:
        remove_key(self._key)
        self._called = False
        super().__exit__(*args, **kwargs)
        with Client((LOCALHOST, self._port), authkey=AUTH_KEY) as conn:
            conn.send(DONE)
        self._server.join()


def empty() -> Dict[str, Any]:
    return dict()


@contextmanager
def add_task(
    desc: str,
    total: int | None = None,
    metrics_func: Callable[[], Dict[str, Any]] = empty,
    id: str = "",
    key: str = "main",
):
    try:
        with Client((LOCALHOST, get_port(key)), authkey=AUTH_KEY) as conn:
            conn.send(HELLO)
            conn.send(
                AddTaskMessage(
                    desc=desc,
                    metrics=metrics_func(),
                    total=total,
                    pid=os.getpid(),
                    id=id,
                )
            )

            def update(
                completed: float | None = None,
                advance: float | None = None,
                desc: str | None = None,
                visible: bool = True,
                refresh: bool = False,
                **metrics: dict[str, Any],
            ) -> None:
                conn.send(
                    ProgressUpdateMessage(
                        pid=os.getpid(),
                        id=id,
                        metrics=metrics,
                        completed=completed,
                        advance=advance,
                        desc=desc,
                        visible=visible,
                        refresh=refresh,
                    )
                )

            yield update
    finally:
        ...


def progress_bar(
    iterable: Iterable[T],
    desc: str,
    total: int | None = None,
    metrics_func: Callable[[], Dict[str, Any]] = empty,
    id: str = "",
    key: str = "main",
) -> Iterable[T]:
    """
    Used within a MultiProgress context to report progress of an iterable to the parent (or same) process.
    """
    if total is None and isinstance(iterable, Sized):
        total = len(iterable)

    if not id:
        id = str(threading.get_ident())

    with add_task(desc, total, metrics_func, id, key) as update:
        for r in iterable:
            update(advance=1)
            yield r
