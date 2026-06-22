import asyncio
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {
            "anomaly.events": [],
            "traffic.state": [],
            "signal.decisions": [],
            "simulation.events": []
        }
        
    def subscribe(self, topic: str, callback: Callable):
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)

    async def publish(self, topic: str, data: Any):
        if topic in self.subscribers:
            for callback in self.subscribers[topic]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)

# Global singleton
event_bus = EventBus()
