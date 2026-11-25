"""Limit how many requests the API accepts each minute."""

import time
from collections import Counter

PER_VISITOR = 60
EVERYONE = 600


class RateLimiter:
    def __init__(self, per_visitor=PER_VISITOR, everyone=EVERYONE, clock=time.monotonic):
        self.per_visitor = per_visitor
        self.everyone = everyone
        self.clock = clock
        self.minute = None
        self.visitors = Counter()
        self.total = 0

    def allow(self, visitor):
        minute = int(self.clock() // 60)
        if minute != self.minute:
            self.minute = minute
            self.visitors.clear()
            self.total = 0

        if self.total >= self.everyone or self.visitors[visitor] >= self.per_visitor:
            return False

        self.total += 1
        self.visitors[visitor] += 1
        return True
