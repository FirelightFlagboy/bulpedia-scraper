import asyncio
from typing import Protocol

from .settings import Settings


class TaskQueue:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[Task] = asyncio.Queue()
        self.lock = asyncio.Lock()


class Task(Protocol):
    def __call__(self, task_queue: TaskQueue, settings: Settings) -> None:
        ...
