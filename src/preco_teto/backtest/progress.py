"""Rich progress helpers for backtest CLI (stderr; silent when disabled)."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Iterator

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

_stderr = Console(stderr=True)


@contextmanager
def backtest_progress(*, enabled: bool) -> Iterator[Progress | None]:
    if not enabled:
        yield None
        return
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=_stderr,
        transient=True,
    )
    with progress:
        yield progress


def track_range(progress: Progress | None, total: int, description: str) -> Iterator[int]:
    """Yield 0..total-1, advancing a progress task when progress is set."""
    if progress is None or total <= 0:
        yield from range(total)
        return
    task_id = progress.add_task(description, total=total)
    for i in range(total):
        yield i
        progress.advance(task_id)


def stage(progress: Progress | None, description: str):
    """Context manager for an indeterminate/one-shot stage."""
    if progress is None:
        return nullcontext()
    task_id = progress.add_task(description, total=1)

    @contextmanager
    def _cm():
        try:
            yield
        finally:
            progress.update(task_id, completed=1)

    return _cm()
