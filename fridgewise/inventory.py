"""The fridge inventory: what is inside, when it expires, and what to eat first."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from .shelf_life import days_for, display_name


@dataclass
class Item:
    key: str                       # food type, e.g. "tofu"
    added: date
    expiry: date
    expiry_source: str             # "label" (read by OCR), "estimate" (shelf-life table) or "manual"
    qty: int = 1

    def days_left(self, today: date) -> int:
        return (self.expiry - today).days

    def status(self, today: date) -> str:
        d = self.days_left(today)
        if d < 0:
            return "expired"
        if d <= 1:
            return "eat today"
        if d <= 3:
            return "eat soon"
        return "ok"

    @property
    def name(self) -> str:
        return display_name(self.key)


@dataclass
class Inventory:
    items: List[Item] = field(default_factory=list)

    def add(self, key: str, added: date, label_expiry: Optional[date] = None, qty: int = 1,
            manual_expiry: Optional[date] = None) -> Item:
        if manual_expiry:
            exp, src = manual_expiry, "manual"
        elif label_expiry:
            exp, src = label_expiry, "label"
        else:
            exp, src = added + timedelta(days=days_for(key)), "estimate"
        item = Item(key=key, added=added, expiry=exp, expiry_source=src, qty=qty)
        self.items.append(item)
        return item

    def remove(self, key: str) -> bool:
        """Take out the item of this type that expires first (the one you would eat)."""
        same = [i for i in self.items if i.key == key]
        if not same:
            return False
        self.items.remove(min(same, key=lambda i: i.expiry))
        return True

    def by_urgency(self, today: date) -> List[Item]:
        return sorted(self.items, key=lambda i: (i.days_left(today), i.key))

    def keys(self) -> set:
        return {i.key for i in self.items}

    # ---- persistence: a small local JSON file, nothing leaves the device ----
    def save(self, path: Path) -> None:
        data = [{**asdict(i), "added": i.added.isoformat(), "expiry": i.expiry.isoformat()} for i in self.items]
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Inventory":
        p = Path(path)
        if not p.exists():
            return cls()
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = [Item(key=r["key"], added=date.fromisoformat(r["added"]), expiry=date.fromisoformat(r["expiry"]),
                      expiry_source=r["expiry_source"], qty=r.get("qty", 1)) for r in raw]
        return cls(items)
