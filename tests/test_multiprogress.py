from enriched_progress import MultiProgress, progress_bar
from rich.console import Console
import io
import pytest
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


@pytest.fixture
def multi_prog() -> MultiProgress:
    _time = 0.0

    def fake_time():
        nonlocal _time
        try:
            return _time
        finally:
            _time += 1

    console = Console(
        file=io.StringIO(),
        force_terminal=True,
        color_system="truecolor",
        width=80,
        height=100,
        legacy_windows=False,
    )

    return MultiProgress(console=console, get_time=fake_time, auto_refresh=False)


def do_work(n: int) -> None:
    for _ in progress_bar(
        range(n+1), desc=str(n+1), id=str(n)
    ):
        ...


@pytest.mark.parametrize("num_workers", (1, 5, 10, 50, 100, 200))
def test_multiprogress_with_threads(multi_prog: MultiProgress, num_workers: int):
    with multi_prog, ThreadPoolExecutor(max_workers=num_workers) as e:
        list(e.map(do_work, range(num_workers)))

    assert len(multi_prog.tasks) == num_workers
    for task in multi_prog.tasks:
        assert task.completed == task.total
    assert set(t.id for t in multi_prog.tasks) == set(range(num_workers))


@pytest.mark.parametrize("num_workers", (1, 5, 10, 50))
def test_multiprogress_with_processes(multi_prog: MultiProgress, num_workers: int):

    with multi_prog, ProcessPoolExecutor(max_workers=num_workers) as e:
        list(e.map(do_work, range(num_workers)))

    assert len(multi_prog.tasks) == num_workers
    for task in multi_prog.tasks:
        assert task.completed == task.total
    assert set(t.id for t in multi_prog.tasks) == set(range(num_workers))
