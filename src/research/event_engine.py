from typing import List, Any, Callable
from datetime import datetime

class EventEngine:
    """Sorts events by timestamp and processes chronologically."""
    def __init__(self, events: List[Any], timestamp_getter: Callable[[Any], datetime]):
        self.events = sorted(events, key=timestamp_getter)
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.events):
            raise StopIteration
        event = self.events[self.index]
        self.index += 1
        return event

    def process(self, callback: Callable[[Any], None]):
        for event in self:
            callback(event)
