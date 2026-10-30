"""Links uploaded in this session (newest first). Not persisted, by design."""


class RecentLinks:
    def __init__(self, limit: int = 5):
        self.limit = limit
        self._items: list[str] = []

    def add(self, url: str) -> None:
        if url in self._items:
            self._items.remove(url)
        self._items.insert(0, url)
        del self._items[self.limit:]

    def items(self) -> list[str]:
        return list(self._items)
