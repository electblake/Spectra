"""Application events, independent of any presentation framework."""

from dataclasses import dataclass, field
from time import perf_counter


@dataclass(frozen=True)
class Log:
    text: str


@dataclass(frozen=True)
class Progress:
    stage: str
    current: int = 0
    total: int | None = None
    timestamp: float = field(default_factory=perf_counter)


def console_report(event):
    if isinstance(event, Log):
        print(event.text)
    elif event.total is None:
        print(event.stage)
    else:
        print(f"{event.stage} {event.current}/{event.total}")
