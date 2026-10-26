# FridgeWise — an on-device AI fridge manager

**ASUS UGen AI League Innovation Hackathon 2026 · Everyday AI · Battlefield Lightning (ASUS UGen300)**

FridgeWise knows what is in your fridge, reads the expiry date off the packaging, tells you what
to eat first and suggests a dish that uses it up — all on a small box next to the fridge, with no
photo of your kitchen ever leaving the house.

## What it does

| Step | How | Stage I (now) | Stage II (UGen300) |
|---|---|---|---|
| **Recognise** food on a shelf or held to the camera | object detection | YOLOv8n, COCO food classes, CPU | model fine-tuned on Taiwanese groceries, compiled for Hailo-10H |
| **Read** the printed date | OCR + date parser | Tesseract + `fridgewise/dates.py` | OCR model on Hailo-10H, same parser |
| **Estimate** a date for unlabelled food | shelf-life table | `fridgewise/shelf_life.py` | same, tuned per household |
| **Prioritise** what to eat | days-left urgency | `fridgewise/inventory.py` | same |
| **Recommend** a dish | urgency-weighted recipe ranking | `fridgewise/recipes.py` | + small on-device LLM writes the steps |

### The date parser handles Taiwanese labels
`2026/11/03`, `2026.11.03`, `20261103`, `2026年11月3日`, **ROC years** such as `115.11.03`
(115 + 1911 = 2026) and day-first imports such as `03/11/2026`. When a label carries both a
manufacturing date (製造日期, MFG) and an expiry date (有效日期, 保存期限, EXP, BB), it takes the
expiry date; with no readable keyword it takes the later date.

### Recipe ranking
`score = Σ urgency(days left) of ingredients in the fridge − 1.5 × missing main ingredients`,
with `urgency = 4 / (1 + days left)` and zero for food that has already expired. The top dish is
the one that rescues the most at-risk food with the fewest extra purchases. In Stage II the
ranked list is handed to a small LLM on the UGen300 to write the steps; the ranking stays
deterministic, so the model cannot suggest food that is not in the fridge.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# OCR engine: macOS `brew install tesseract tesseract-lang`, Ubuntu `sudo apt install tesseract-ocr tesseract-ocr-chi-tra`
```

## Run

```bash
python app.py demo                                   # seeded fridge: priorities + what to cook
python app.py scan-label samples/label_milk.jpg milk # OCR an expiry date and add the item
python app.py scan-label photo.jpg tofu --lang eng+chi_tra
python app.py scan-shelf fridge_shelf.jpg            # detect produce in a shelf photo (COCO, fast)
python app.py scan-shelf fridge_shelf.jpg --open-vocab  # YOLO-World with our own food list
python app.py add banana                             # add by hand (shelf-life estimate)
python app.py eat tofu                               # take one out
python app.py list                                   # eat-first list
python app.py suggest                                # what to cook tonight
python app.py prompt                                 # the prompt the on-device LLM gets
```
Add `--today 2026-10-27` to simulate another day. The inventory lives in `fridge.json` on this
machine; photos are processed in memory and never saved.

Example (`python app.py demo --today 2026-10-27`):
```
In your fridge on 2026-10-27 (eat from the top):
  [X]   Milk 鮮奶                expires 1 day ago    (label)
  [!!]  Pork (raw) 豬肉          expires in 1 day     (estimate)
  [!!]  Tofu 豆腐                expires in 1 day     (label)
  [!]   Tomato 番茄              expires in 2 days    (estimate)
  ...
Cook tonight:
  1. Braised tofu with pork 家常豆腐  (score 5.0)  rescues tofu, pork, scallion
  2. Miso soup with tofu 味噌豆腐湯  (score 3.0)  rescues tofu, scallion
  3. Tomato and egg stir-fry 番茄炒蛋  (score 2.64)  rescues tomato, scallion
```

## Tests

```bash
python -m pytest -q
```
13 tests cover the date formats (incl. ROC years and MFG-vs-EXP), inventory status and ordering,
saving/loading, and recipe ranking. They need no camera or model.

## Stage I measurements (laptop-class CPU)

| Check | Result |
|---|---|
| Label OCR, ROC-year tofu label (`samples/label_tofu.jpg`) | read 115.10.28 → 2026-10-28, correct |
| Label OCR, western milk label (`samples/label_milk.jpg`) | MFG skipped, EXP 2026-10-30, correct |
| COCO detector (YOLOv8n) on a mixed-fruit photo | 112 ms per image; found the orange (83%), but called a lemon and kiwi "orange" and missed banana and cabbage |

The detector result is the reason for Stage II: COCO weights know only ~7 foods. The
`--open-vocab` option (YOLO-World) takes our own food list in plain words, and Stage II
fine-tunes on photos of ~30 common Taiwanese groceries. (`--open-vocab` downloads a small text
encoder on first use.)

## Roadmap

| Stage | Milestone |
|---|---|
| **I (now)** | CPU prototype: label OCR, date parsing, produce detection, eat-first list, recipe ranking |
| **II (Nov 6 – Dec 4)** | Detection + OCR on the UGen300; fine-tune on ~30 common Taiwanese groceries; on-device LLM recipes; measure accuracy, latency and power vs CPU |
| **Pilot** | A few student and family households for two weeks: food thrown away before vs after |

## Limitations

Shelf-life estimates are conservative defaults, not food-safety guarantees: always check the food.
COCO weights only know a handful of foods; Stage II adds a fine-tuned detector.

## Layout

```
app.py                    command-line demo
fridgewise/dates.py       expiry-date finder (OCR text -> date)
fridgewise/shelf_life.py  default fridge life for unlabelled food
fridgewise/inventory.py   items, urgency, local JSON store
fridgewise/recipes.py     urgency-weighted recipe ranking + LLM prompt
fridgewise/vision.py      food detector and label OCR (optional imports)
samples/                  two synthetic label photos for the OCR demo
tests/                    unit tests
```
