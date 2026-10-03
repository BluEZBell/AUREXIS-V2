from abc import ABC, abstractmethod
from src.core.event_bus import EventBus, TickEvent
from src.core.config import setup_logger
logger = setup_logger("strategy")

class BaseStrategy(ABC):
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.event_bus.subscribe(TickEvent, self.process_tick)

    @abstractmethod
    async def process_tick(self, event: TickEvent):
        pass

