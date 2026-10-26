"""Find the expiry date in text read off a food label by OCR.

Handles the formats seen on Taiwanese packaging:
  * 2026/11/03, 2026.11.03, 2026-11-03, 20261103
  * ROC (Minguo) years: 115/11/03, 115.11.03  (115 + 1911 = 2026)
  * 2026年11月3日
  * day-first imports: 03/11/2026 (only when the year is last)
and prefers the date next to an expiry keyword (有效日期, 保存期限, 賞味期限, EXP, BB, Best before)
over a manufacturing date (製造日期, MFG).
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple

EXPIRY_KEYWORDS = ["有效日期", "有效期限", "保存期限", "賞味期限", "到期日", "exp", "best before", "bb", "use by"]
MFG_KEYWORDS = ["製造日期", "製造日", "生產日期", "mfg", "mfd", "prod"]

_SEP = r"[./\-\s]"
PATTERNS = [
    # 2026年11月3日
    ("ymd_cjk", re.compile(r"(\d{2,4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")),
    # 2026/11/03 or ROC 115/11/03
    ("ymd", re.compile(rf"(?<!\d)(\d{{3,4}}){_SEP}(\d{{1,2}}){_SEP}(\d{{1,2}})(?!\d)")),
    # 20261103
    ("ymd_compact", re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")),
    # 03/11/2026 (day first, year last)
    ("dmy", re.compile(rf"(?<!\d)(\d{{1,2}}){_SEP}(\d{{1,2}}){_SEP}(20\d{{2}})(?!\d)")),
]


def _to_year(y: int) -> int:
    if 100 <= y <= 199:      # ROC calendar
        return y + 1911
    if 10 <= y <= 99:        # two-digit western year
        return 2000 + y
    return y


def _make(y: int, m: int, d: int) -> Optional[date]:
    try:
        dt = date(_to_year(y), m, d)
    except ValueError:
        return None
    if not (2000 <= dt.year <= 2100):
        return None
    return dt


def find_dates(text: str) -> List[Tuple[int, date]]:
    """All plausible dates in the text with their character position."""
    found: List[Tuple[int, date]] = []
    taken = []
    for kind, pat in PATTERNS:
        for m in pat.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            a, b, c = (int(g) for g in m.groups())
            dt = _make(c, b, a) if kind == "dmy" else _make(a, b, c)
            if dt:
                found.append((m.start(), dt))
                taken.append((m.start(), m.end()))
    return sorted(found)


def _nearest_keyword_distance(text_lower: str, pos: int, keywords) -> int:
    best = 10**9
    for kw in keywords:
        for m in re.finditer(re.escape(kw), text_lower):
            if m.end() <= pos + 1:           # keyword before the date
                best = min(best, pos - m.end())
    return best


def parse_expiry(text: str) -> Optional[date]:
    """Best guess at the expiry date, or None if no date is found."""
    dates = find_dates(text)
    if not dates:
        return None
    low = text.lower()
    scored = []
    for pos, dt in dates:
        exp_d = _nearest_keyword_distance(low, pos, EXPIRY_KEYWORDS)
        mfg_d = _nearest_keyword_distance(low, pos, MFG_KEYWORDS)
        if exp_d < mfg_d:
            score = 0          # clearly labelled as expiry
        elif mfg_d < exp_d:
            score = 2          # clearly a manufacturing date
        else:
            score = 1          # unlabelled
        scored.append((score, -dt.toordinal(), dt))  # unlabelled: prefer the later date
    scored.sort()
    best = scored[0]
    if best[0] == 2:
        return None            # only manufacturing dates were found
    return best[2]
