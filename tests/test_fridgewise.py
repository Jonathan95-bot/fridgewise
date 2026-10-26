from datetime import date, timedelta

from fridgewise import Inventory, find_dates, parse_expiry, score_recipes
from fridgewise.recipes import urgency

TODAY = date(2026, 10, 27)


# ---------------- expiry date parsing ----------------
def test_western_formats():
    assert parse_expiry("有效日期: 2026/11/03") == date(2026, 11, 3)
    assert parse_expiry("EXP 2026.11.03") == date(2026, 11, 3)
    assert parse_expiry("BB 20261103") == date(2026, 11, 3)
    assert parse_expiry("2026年11月3日") == date(2026, 11, 3)


def test_roc_year():
    assert parse_expiry("有效日期 115.11.03") == date(2026, 11, 3)
    assert parse_expiry("保存期限:115/01/09") == date(2026, 1, 9)


def test_day_first_import():
    assert parse_expiry("Best before 03/11/2026") == date(2026, 11, 3)


def test_prefers_expiry_over_manufacture_date():
    text = "製造日期 2026/10/20  有效日期 2026/11/03"
    assert parse_expiry(text) == date(2026, 11, 3)
    text2 = "MFG 2026.10.20 EXP 2026.10.30"
    assert parse_expiry(text2) == date(2026, 10, 30)


def test_only_manufacture_date_returns_none():
    assert parse_expiry("製造日期 2026/10/20") is None


def test_unlabelled_takes_later_date():
    assert parse_expiry("2026/10/20 2026/11/15") == date(2026, 11, 15)


def test_rejects_impossible_dates_and_noise():
    assert parse_expiry("2026/13/40") is None
    assert parse_expiry("淨重 500g 電話 02-2345-6789") is None
    assert find_dates("no dates here") == []


# ---------------- inventory ----------------
def test_label_beats_estimate_and_status():
    inv = Inventory()
    a = inv.add("tofu", TODAY, label_expiry=TODAY + timedelta(days=1))
    b = inv.add("tomato", TODAY - timedelta(days=5))         # 7-day estimate -> 2 days left
    c = inv.add("milk", TODAY - timedelta(days=9), label_expiry=TODAY - timedelta(days=1))
    assert a.expiry_source == "label" and b.expiry_source == "estimate"
    assert a.status(TODAY) == "eat today"
    assert b.status(TODAY) == "eat soon"
    assert c.status(TODAY) == "expired"
    assert [i.key for i in inv.by_urgency(TODAY)] == ["milk", "tofu", "tomato"]


def test_eat_removes_earliest_expiring(tmp_path):
    inv = Inventory()
    inv.add("egg", TODAY, label_expiry=TODAY + timedelta(days=10))
    inv.add("egg", TODAY, label_expiry=TODAY + timedelta(days=2))
    assert inv.remove("egg")
    assert inv.items[0].expiry == TODAY + timedelta(days=10)
    p = tmp_path / "fridge.json"
    inv.save(p)
    assert Inventory.load(p).items[0].expiry == TODAY + timedelta(days=10)


# ---------------- recipes ----------------
def test_urgency_shape():
    assert urgency(0) > urgency(1) > urgency(3) > urgency(7) > 0
    assert urgency(-1) == 0


def test_recipe_rescues_expiring_food():
    inv = Inventory()
    inv.add("tofu", TODAY, label_expiry=TODAY)                       # expires today
    inv.add("scallion", TODAY - timedelta(days=4))                   # 3 days left
    inv.add("egg", TODAY, label_expiry=TODAY + timedelta(days=14))
    inv.add("tomato", TODAY)                                         # 7 days left
    top = score_recipes(inv, TODAY)
    assert top[0]["recipe"].name_zh == "味噌豆腐湯"
    assert "tofu" in top[0]["rescues"]


def test_no_suggestion_that_needs_more_shopping_than_it_saves():
    inv = Inventory()
    inv.add("tofu", TODAY, label_expiry=TODAY + timedelta(days=6))   # low urgency
    names = [r["recipe"].name_zh for r in score_recipes(inv, TODAY)]
    assert "家常豆腐" not in names                                     # needs pork + scallion


def test_expired_food_is_not_used():
    inv = Inventory()
    inv.add("milk", TODAY, label_expiry=TODAY - timedelta(days=2))
    inv.add("banana", TODAY, label_expiry=TODAY + timedelta(days=1))   # ripe banana
    top = score_recipes(inv, TODAY)
    assert top[0]["recipe"].name_zh == "香蕉牛奶"
    assert "milk" in top[0]["missing"]
