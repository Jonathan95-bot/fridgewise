"""Camera-side models: food detection and label OCR.

Both are optional imports so the core logic (dates, inventory, recipes) runs and is testable
without any model installed.

Stage I backends (laptop CPU):
  * detection: Ultralytics YOLO (COCO weights recognise banana, apple, orange, broccoli, carrot,
    sandwich, cake...; Stage II fine-tunes on Taiwanese groceries)
  * OCR: Tesseract via pytesseract
Stage II backends: the same models exported to ONNX and compiled for the Hailo-10H on the ASUS UGen300.
"""
from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

# COCO class name -> our food key
COCO_TO_FOOD = {
    "banana": "banana", "apple": "apple", "orange": "orange", "broccoli": "broccoli",
    "carrot": "carrot", "sandwich": "sandwich", "cake": "cake",
}


class FoodDetector:
    """COCO detector: fast, but only knows a handful of foods."""

    def __init__(self, weights: str = "yolov8n.pt", conf: float = 0.35):
        from ultralytics import YOLO  # imported lazily
        self.model = YOLO(weights)
        self.conf = conf
        self.label_map = COCO_TO_FOOD

    def detect(self, image_bgr: np.ndarray) -> List[Tuple[str, float, Tuple[int, int, int, int]]]:
        res = self.model(image_bgr, conf=self.conf, verbose=False)[0]
        out = []
        for box in res.boxes:
            cls_name = res.names[int(box.cls)]
            if cls_name in self.label_map:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                out.append((self.label_map[cls_name], float(box.conf), (x1, y1, x2, y2)))
        return out


# Open-vocabulary prompts -> our food keys (any food in shelf_life.py can be added here, no training)
OPEN_VOCAB = {
    "banana": "banana", "apple": "apple", "orange": "orange", "broccoli": "broccoli", "carrot": "carrot",
    "cabbage": "cabbage", "tomato": "tomato", "green bell pepper": "green_pepper", "spinach": "spinach",
    "green onion": "scallion", "egg": "egg", "block of tofu": "tofu", "milk carton": "milk",
    "raw pork": "pork", "raw chicken": "chicken", "fish": "fish", "sandwich": "sandwich", "cake": "cake",
}


class OpenVocabFoodDetector(FoodDetector):
    """YOLO-World: detects foods named in plain words, so local groceries need no retraining.

    First use downloads a small CLIP text encoder once (needs internet), then runs offline.
    """

    def __init__(self, weights: str = "yolov8s-worldv2.pt", conf: float = 0.2):
        from ultralytics import YOLOWorld  # imported lazily
        self.model = YOLOWorld(weights)
        self.model.set_classes(list(OPEN_VOCAB))
        self.conf = conf
        self.label_map = OPEN_VOCAB


def preprocess_label(image_bgr: np.ndarray) -> np.ndarray:
    """Grey, upscale, binarise: printed dates on curved, glossy packaging OCR far better this way."""
    grey = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    h = grey.shape[0]
    if h < 600:
        grey = cv2.resize(grey, None, fx=600 / h, fy=600 / h, interpolation=cv2.INTER_CUBIC)
    grey = cv2.bilateralFilter(grey, 7, 50, 50)
    return cv2.adaptiveThreshold(grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)


def read_label_text(image_bgr: np.ndarray, lang: str = "eng") -> str:
    import pytesseract  # imported lazily
    img = preprocess_label(image_bgr)
    return pytesseract.image_to_string(img, lang=lang, config="--psm 6")
