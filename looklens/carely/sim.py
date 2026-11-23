"""Virtual radar for demos and testing without hardware: one simulated person
walks between rooms, sits, lies down or falls, and every radar sends what it
would see once a second, through the same path as real readings."""

import asyncio
import random
import time

from .radar import Reading

HEIGHTS = {"stand": 152, "walk": 150, "sit": 110, "lie": 65, "fall": 25}


class VirtualHome:
    def __init__(self, hub):
        self.hub = hub
        self.running = False
        self.room: str | None = None
        self.pose = "stand"
        self.moving = False
        self.task: asyncio.Task | None = None

    def state(self) -> dict:
        return {"running": self.running, "room": self.room, "pose": self.pose, "moving": self.moving}

    async def act(self, action: str, room: str | None = None) -> dict:
        if action == "stop":
            self.running = False
            if self.task:
                self.task.cancel()
                self.task = None
            return self.state()
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._loop())
        if room:
            self.room = room
        if action == "enter":
            self.pose, self.moving = "walk", True
        elif action == "leave":
            self.room = None
        elif action in ("stand", "walk"):
            self.pose, self.moving = action, action == "walk"
        elif action in ("sit", "lie"):
            self.pose, self.moving = action, False
        elif action == "fall":
            self.pose, self.moving = "fall", False
        elif action == "getup":
            self.pose, self.moving = "stand", True
        elif action == "wiggle":
            self.moving = not self.moving
        await self._emit()  # react immediately, not on the next second
        return self.state()

    async def _loop(self) -> None:
        while self.running:
            await asyncio.sleep(1.0)
            await self._emit()

    async def _emit(self) -> None:
        now = time.time()
        for d in self.hub.s.devices.values():
            here = self.room == d.id
            if not here:
                await self.hub.ingest(Reading(d.id, now, presence=False))
                continue
            h = HEIGHTS[self.pose] + random.uniform(-4, 4)
            await self.hub.ingest(Reading(
                d.id, now, presence=True,
                moving_energy=random.randint(35, 80) if self.moving else random.randint(0, 8),
                still_energy=random.randint(40, 70),
                distance_cm=round(d.ceiling_cm - h),
            ))
