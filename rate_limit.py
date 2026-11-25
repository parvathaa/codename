"""Limit how many requests the API accepts each minute, from everyone together.

Netlify limits each visitor, because it can see who is really connecting.
"""

import time

PER_MINUTE = 600


class RateLimiter:
    def __init__(self, per_minute=PER_MINUTE, clock=time.monotonic):
        self.per_minute = per_minute
        self.clock = clock
        self.minute = None
        self.total = 0

    def allow(self):
        minute = int(self.clock() // 60)
        if minute != self.minute:
            self.minute = minute
            self.total = 0

        if self.total >= self.per_minute:
            return False
        self.total += 1
        return True
