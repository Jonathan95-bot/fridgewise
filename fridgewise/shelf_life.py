"""Default refrigerated shelf life, used when a food has no printed date (fresh produce, leftovers).

Values are conservative starting estimates in days for refrigerated storage, loosely based on
public food-storage guidance such as the USDA FoodKeeper. They are meant to be tuned per household.
"""
from __future__ import annotations

from typing import Dict, Optional

# key -> (display name, Chinese name, days in the fridge)
SHELF_LIFE: Dict[str, tuple] = {
    "banana":    ("Banana", "香蕉", 5),
    "apple":     ("Apple", "蘋果", 21),
    "orange":    ("Orange", "柳橙", 14),
    "broccoli":  ("Broccoli", "花椰菜", 5),
    "carrot":    ("Carrot", "紅蘿蔔", 21),
    "cabbage":   ("Cabbage", "高麗菜", 14),
    "tomato":    ("Tomato", "番茄", 7),
    "green_pepper": ("Green pepper", "青椒", 7),
    "spinach":   ("Spinach", "菠菜", 4),
    "scallion":  ("Scallion", "蔥", 7),
    "egg":       ("Eggs", "雞蛋", 21),
    "tofu":      ("Tofu", "豆腐", 4),
    "milk":      ("Milk", "鮮奶", 7),
    "pork":      ("Pork (raw)", "豬肉", 2),
    "chicken":   ("Chicken (raw)", "雞肉", 2),
    "fish":      ("Fish (raw)", "魚", 2),
    "leftovers": ("Leftovers", "剩菜", 3),
    "sandwich":  ("Sandwich", "三明治", 2),
    "cake":      ("Cake", "蛋糕", 4),
}

DEFAULT_DAYS = 5


def days_for(key: str) -> int:
    return SHELF_LIFE.get(key, (None, None, DEFAULT_DAYS))[2]


def display_name(key: str) -> str:
    entry: Optional[tuple] = SHELF_LIFE.get(key)
    return f"{entry[0]} {entry[1]}" if entry else key
