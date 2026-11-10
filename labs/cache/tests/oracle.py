"""Slow reference models: Python lists and unpacked counters, no native cache code."""

MASK = (1 << 64) - 1


def mix(value: int) -> int:
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK
    return value ^ (value >> 31)


class Model:
    def __init__(self, algorithm: str, capacity: int, window: int, protected: int, aging: int):
        self.algorithm, self.capacity = algorithm, capacity
        self.window_capacity = max(1, capacity * window // 100) if capacity else 0
        main = capacity - self.window_capacity if algorithm == "wtinylfu" else capacity
        self.protected_capacity = main * protected // 100
        self.main_capacity = main
        self.recent, self.frequent, self.window = [], [], []
        self.b1, self.b2, self.target = [], [], 0
        self.frequencies = {}
        self.time, self.last = 0, {}
        self.interval, self.samples = max(1, capacity * aging), 0
        self.width = 64
        while self.width < capacity * 4:
            self.width *= 2
        self.sketch = [[0] * self.width for _ in range(4)]

    def resident(self) -> list[int]:
        return sorted(self.recent + self.frequent + self.window)

    def record(self, key: int) -> None:
        seeds = [0x243F6A8885A308D3, 0x13198A2E03707344, 0xA4093822299F31D0, 0x082EFA98EC4E6C89]
        for row, seed in enumerate(seeds):
            index = mix(key ^ seed) % self.width
            self.sketch[row][index] = min(15, self.sketch[row][index] + 1)
        self.samples += 1
        if self.samples == self.interval:
            self.sketch = [[counter // 2 for counter in row] for row in self.sketch]
            self.samples = 0

    def estimate(self, key: int) -> int:
        seeds = [0x243F6A8885A308D3, 0x13198A2E03707344, 0xA4093822299F31D0, 0x082EFA98EC4E6C89]
        return min(self.sketch[row][mix(key ^ seed) % self.width] for row, seed in enumerate(seeds))

    @staticmethod
    def touch(queue: list[int], key: int) -> None:
        queue.remove(key)
        queue.append(key)

    def segment_hit(self, key: int) -> bool:
        if key in self.frequent:
            self.touch(self.frequent, key)
            return True
        if key in self.recent:
            self.recent.remove(key)
            self.frequent.append(key)
            if len(self.frequent) > self.protected_capacity:
                self.recent.append(self.frequent.pop(0))
            return True
        return False

    def replace(self, b2_hit: bool) -> None:
        if self.recent and (
            len(self.recent) > self.target or (b2_hit and len(self.recent) == self.target)
        ):
            self.b1.append(self.recent.pop(0))
        else:
            self.b2.append(self.frequent.pop(0))

    def access(self, key: int) -> bool:
        self.time += 1
        if self.algorithm == "wtinylfu":
            self.record(key)
            if key in self.window:
                self.touch(self.window, key)
                return True
            if self.segment_hit(key):
                return True
            if self.capacity:
                self.window.append(key)
                if len(self.window) > self.window_capacity:
                    candidate = self.window.pop(0)
                    if self.main_capacity:
                        if len(self.recent) + len(self.frequent) < self.main_capacity:
                            self.recent.append(candidate)
                        elif self.estimate(candidate) > self.estimate(self.recent[0]):
                            self.recent.pop(0)
                            self.recent.append(candidate)
            return False
        if self.algorithm == "slru":
            if self.segment_hit(key):
                return True
            if self.capacity:
                if len(self.recent) + len(self.frequent) == self.capacity:
                    self.recent.pop(0)
                self.recent.append(key)
            return False
        if self.algorithm == "arc":
            if key in self.recent:
                self.recent.remove(key)
                self.frequent.append(key)
                return True
            if key in self.frequent:
                self.touch(self.frequent, key)
                return True
            if not self.capacity:
                return False
            if key in self.b1:
                self.target = min(self.capacity, self.target + max(1, len(self.b2) // len(self.b1)))
                self.replace(False)
                self.b1.remove(key)
                self.frequent.append(key)
            elif key in self.b2:
                self.target = max(0, self.target - max(1, len(self.b1) // len(self.b2)))
                self.replace(True)
                self.b2.remove(key)
                self.frequent.append(key)
            else:
                if len(self.recent) + len(self.b1) == self.capacity:
                    if len(self.recent) < self.capacity:
                        self.b1.pop(0)
                        self.replace(False)
                    else:
                        self.recent.pop(0)
                elif len(self.resident()) + len(self.b1) + len(self.b2) >= self.capacity:
                    if len(self.resident()) + len(self.b1) + len(self.b2) == 2 * self.capacity:
                        self.b2.pop(0)
                    self.replace(False)
                self.recent.append(key)
            return False
        if key in self.recent:
            self.last[key] = self.time
            self.frequencies[key] += 1
            if self.algorithm == "lru":
                self.touch(self.recent, key)
            return True
        if self.capacity:
            if len(self.recent) == self.capacity:
                victim = (
                    min(self.recent, key=lambda k: (self.frequencies[k], self.last[k]))
                    if self.algorithm == "lfu"
                    else self.recent[0]
                )
                self.recent.remove(victim)
                del self.frequencies[victim], self.last[victim]
            self.recent.append(key)
            self.frequencies[key], self.last[key] = 1, self.time
        return False
