"""Recipe recommendation that rewards using up the food closest to expiry.

Score for a recipe =
    sum over its ingredients that are in the fridge of urgency(days_left)
  - MISSING_PENALTY x number of main ingredients that are not in the fridge

urgency() is large for food that expires today and fades for food with plenty of time,
so the top recipe is the one that rescues the most at-risk food with the fewest extra purchases.

Stage I ranks a built-in recipe list. Stage II passes the ranked list and the at-risk items
to a small on-device LLM (UGen300) to adapt the recipe and write the steps; the ranking stays
deterministic so the model cannot suggest food that is not in the fridge.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

from .inventory import Inventory

MISSING_PENALTY = 1.5
PANTRY = {"salt", "oil", "soy_sauce", "sugar", "garlic", "rice", "noodles", "flour", "miso"}


@dataclass(frozen=True)
class Recipe:
    name: str
    name_zh: str
    ingredients: tuple   # main ingredient keys (pantry staples are assumed)


RECIPES: List[Recipe] = [
    Recipe("Tomato and egg stir-fry", "番茄炒蛋", ("tomato", "egg", "scallion")),
    Recipe("Pork with green pepper", "青椒炒肉絲", ("pork", "green_pepper")),
    Recipe("Stir-fried cabbage", "炒高麗菜", ("cabbage", "carrot")),
    Recipe("Scallion omelette", "蔥花蛋", ("egg", "scallion")),
    Recipe("Miso soup with tofu", "味噌豆腐湯", ("tofu", "scallion")),
    Recipe("Braised tofu with pork", "家常豆腐", ("tofu", "pork", "scallion")),
    Recipe("Garlic broccoli", "蒜炒花椰菜", ("broccoli",)),
    Recipe("Banana milk smoothie", "香蕉牛奶", ("banana", "milk")),
    Recipe("Spinach and egg soup", "菠菜蛋花湯", ("spinach", "egg")),
    Recipe("Chicken and broccoli stir-fry", "花椰菜炒雞丁", ("chicken", "broccoli", "carrot")),
    Recipe("Steamed fish with scallion", "蔥油蒸魚", ("fish", "scallion")),
    Recipe("Fried rice with leftovers", "剩菜炒飯", ("leftovers", "egg", "scallion")),
]


def urgency(days_left: int) -> float:
    if days_left < 0:
        return 0.0          # already expired: do not build a meal around it
    return 4.0 / (1 + days_left)   # today=4.0, 1 day=2.0, 3 days=1.0, 7 days=0.5


def score_recipes(inv: Inventory, today: date, recipes: List[Recipe] = RECIPES, top: int = 3) -> List[Dict]:
    best_by_key: Dict[str, int] = {}
    for item in inv.items:
        d = item.days_left(today)
        if d >= 0:
            best_by_key[item.key] = min(d, best_by_key.get(item.key, d))
    results = []
    for r in recipes:
        have = [k for k in r.ingredients if k in best_by_key]
        missing = [k for k in r.ingredients if k not in best_by_key and k not in PANTRY]
        if not have:
            continue
        score = sum(urgency(best_by_key[k]) for k in have) - MISSING_PENALTY * len(missing)
        if score <= 0:
            continue   # needs more shopping than it saves: not worth suggesting
        rescues = [k for k in have if best_by_key[k] <= 3]
        results.append({"recipe": r, "score": round(score, 2), "uses": have,
                        "missing": missing, "rescues": rescues})
    results.sort(key=lambda x: (-x["score"], len(x["missing"]), x["recipe"].name))
    return results[:top]


def llm_prompt(ranked: List[Dict], inv: Inventory, today: date) -> str:
    """Prompt for the on-device LLM (Stage II). Only facts from the inventory and the ranking."""
    at_risk = [f"{i.name} ({i.days_left(today)} day(s) left)" for i in inv.by_urgency(today)
               if 0 <= i.days_left(today) <= 3]
    lines = [f"- {x['recipe'].name} ({x['recipe'].name_zh}); missing: {', '.join(x['missing']) or 'nothing'}"
             for x in ranked]
    return ("You are a home cook. Pick the first recipe below, write it in at most 5 short steps for 1-2 "
            "people, and use only ingredients from the fridge list plus basic pantry staples.\n"
            f"Use first: {', '.join(at_risk) or 'nothing urgent'}.\nRanked recipes:\n" + "\n".join(lines))
