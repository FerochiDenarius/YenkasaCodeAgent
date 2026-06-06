from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException

from app.config.settings import Settings


@dataclass
class _Bucket:
    timestamps: deque[float]
    tokens: float
    updated_at: float


class RateLimiter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._buckets: dict[str, _Bucket] = defaultdict(
            lambda: _Bucket(timestamps=deque(), tokens=float(settings.rate_limit_burst), updated_at=time.monotonic())
        )

    async def check(self, key: str, *, expensive: bool = False) -> None:
        now = time.monotonic()
        per_minute = self.settings.expensive_rate_limit_per_minute if expensive else self.settings.rate_limit_per_minute
        window = 60.0
        async with self._lock:
            bucket = self._buckets[key]
            while bucket.timestamps and now - bucket.timestamps[0] > window:
                bucket.timestamps.popleft()

            elapsed = now - bucket.updated_at
            bucket.updated_at = now
            refill_per_second = self.settings.rate_limit_burst / window
            bucket.tokens = min(float(self.settings.rate_limit_burst), bucket.tokens + elapsed * refill_per_second)

            if len(bucket.timestamps) >= per_minute or bucket.tokens < 1.0:
                raise HTTPException(status_code=429, detail="Rate limit exceeded.")

            bucket.timestamps.append(now)
            bucket.tokens -= 1.0
