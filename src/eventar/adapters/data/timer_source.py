from typing import Iterator
from eventar.data import TimerEvent, DataEventSource

class TimerSource(DataEventSource):
    def __init__(self, start: int, end: int, step: int = 1) -> None:
        self.range = range(start, end, step)

    def __iter__(self) -> Iterator[TimerEvent]:
        for ts in self.range:
            yield TimerEvent(ts)