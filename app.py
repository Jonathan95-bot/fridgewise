"""FridgeWise command-line demo.

  python app.py demo                         # seeded fridge: priorities + recipe suggestions
  python app.py scan-label photo.jpg tofu    # OCR the expiry date on a package and add the item
  python app.py scan-shelf fridge.jpg        # detect produce in a photo of a shelf and add it
  python app.py add banana                   # add an item by hand (shelf-life estimate)
  python app.py eat tofu                     # take one out
  python app.py list                         # what to eat first
  python app.py suggest                      # what to cook tonight

Everything stays on this machine: the inventory is a local JSON file and photos are never saved.
Use --today YYYY-MM-DD to simulate another day.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

from fridgewise import Inventory, llm_prompt, parse_expiry, score_recipes

STORE = Path("fridge.json")
ICON = {"expired": "[X]", "eat today": "[!!]", "eat soon": "[!]", "ok": "[ ]"}


def print_list(inv: Inventory, today: date) -> None:
    print(f"\nIn your fridge on {today.isoformat()} (eat from the top):")
    for i in inv.by_urgency(today):
        d = i.days_left(today)
        def days(n): return f"{n} day" + ("" if n == 1 else "s")
        when = f"{days(-d)} ago" if d < 0 else ("today" if d == 0 else f"in {days(d)}")
        print(f"  {ICON[i.status(today)]:5} {i.name:22} expires {when:12} ({i.expiry_source})")


def print_suggestions(inv: Inventory, today: date) -> None:
    ranked = score_recipes(inv, today)
    print("\nCook tonight:")
    if not ranked:
        print("  Nothing to suggest yet - add some food first.")
        return
    for n, r in enumerate(ranked, 1):
        rec = r["recipe"]
        extra = f"; buy: {', '.join(r['missing'])}" if r["missing"] else ""
        rescue = f"  rescues {', '.join(r['rescues'])}" if r["rescues"] else ""
        print(f"  {n}. {rec.name} {rec.name_zh}  (score {r['score']}){rescue}{extra}")


def seed_demo(today: date) -> Inventory:
    inv = Inventory()
    inv.add("tofu", today - timedelta(days=3), label_expiry=today + timedelta(days=1))
    inv.add("tomato", today - timedelta(days=5))            # estimate: 7 days -> 2 left
    inv.add("egg", today - timedelta(days=4), label_expiry=today + timedelta(days=12))
    inv.add("scallion", today - timedelta(days=4))          # estimate: 7 days -> 3 left
    inv.add("pork", today - timedelta(days=1))              # estimate: 2 days -> 1 left
    inv.add("green_pepper", today - timedelta(days=1))
    inv.add("milk", today - timedelta(days=9), label_expiry=today - timedelta(days=1))
    inv.add("carrot", today - timedelta(days=2))
    return inv


def main() -> None:
    p = argparse.ArgumentParser(description="FridgeWise - on-device fridge manager")
    p.add_argument("cmd", choices=["demo", "scan-label", "scan-shelf", "add", "eat", "list", "suggest", "prompt"])
    p.add_argument("args", nargs="*")
    p.add_argument("--today", default=None)
    p.add_argument("--lang", default="eng", help="Tesseract languages, e.g. eng+chi_tra")
    p.add_argument("--open-vocab", action="store_true",
                   help="scan-shelf with YOLO-World and our own food list (better coverage, slower)")
    a = p.parse_args()
    today = date.fromisoformat(a.today) if a.today else date.today()

    if a.cmd == "demo":
        inv = seed_demo(today)
        print_list(inv, today)
        print_suggestions(inv, today)
        inv.save(STORE)
        return

    inv = Inventory.load(STORE)

    if a.cmd == "scan-label":
        import cv2
        from fridgewise.vision import read_label_text
        photo, key = a.args[0], a.args[1]
        text = read_label_text(cv2.imread(photo), lang=a.lang)
        exp = parse_expiry(text)
        item = inv.add(key, today, label_expiry=exp)
        print(f"OCR text: {text.strip()!r}")
        print(f"Added {item.name}, expires {item.expiry} ({item.expiry_source})")
    elif a.cmd == "scan-shelf":
        import cv2
        from fridgewise.vision import FoodDetector, OpenVocabFoodDetector
        detector = OpenVocabFoodDetector() if a.open_vocab else FoodDetector()
        found = detector.detect(cv2.imread(a.args[0]))
        for key, conf, _ in found:
            inv.add(key, today)
            print(f"Detected {key} ({conf:.0%})")
        if not found:
            print("No known food detected.")
    elif a.cmd == "add":
        item = inv.add(a.args[0], today)
        print(f"Added {item.name}, estimated to keep until {item.expiry}")
    elif a.cmd == "eat":
        print("Removed." if inv.remove(a.args[0]) else "Not in the fridge.")
    elif a.cmd == "list":
        print_list(inv, today)
    elif a.cmd == "suggest":
        print_suggestions(inv, today)
    elif a.cmd == "prompt":
        print(llm_prompt(score_recipes(inv, today), inv, today))
    inv.save(STORE)


if __name__ == "__main__":
    main()
