import threading
import time
from collections import deque


class MinuteRateLimiter:
    """简单滑动窗口：每分钟最多 n 次操作。"""

    def __init__(self, max_per_minute: int = 30):
        self.max_per_minute = max_per_minute
        self._times = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.time()
            while self._times and now - self._times[0] > 60:
                self._times.popleft()
            if len(self._times) >= self.max_per_minute:
                sleep_s = 60 - (now - self._times[0]) + 0.05
                if sleep_s > 0:
                    time.sleep(sleep_s)
                now = time.time()
                while self._times and now - self._times[0] > 60:
                    self._times.popleft()
            self._times.append(time.time())
