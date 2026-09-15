"""Operation deadlines and cancellation checkpoints shared by processing stages."""

import asyncio
from contextvars import ContextVar

import anyio

CURRENT_DEADLINE: ContextVar[float | None] = ContextVar("web_read_deadline", default=None)


def operation_deadline(seconds: float) -> float:
    return CURRENT_DEADLINE.get() or (asyncio.get_running_loop().time() + seconds)


async def checkpoint(deadline: float | None = None) -> None:
    # timeout_at(past) alone only schedules cancellation for the next loop iteration.
    # An immediately completing HTTP transport/processor could otherwise start new work.
    await anyio.lowlevel.checkpoint()
    effective = deadline if deadline is not None else CURRENT_DEADLINE.get()
    if effective is not None and asyncio.get_running_loop().time() >= effective:
        raise TimeoutError
