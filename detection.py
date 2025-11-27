"""
Object detection using YOLO
"""
import numpy as np
from typing import List
from ultralytics import YOLO

from config import Config, TARGET_CLASS_NAMES
from models import DetectedObject


class ObjectDetector:
    """Handles YOLO-based object detection"""
    
    def __init__(self):
        self.model = YOLO(Config.YOLO_MODEL)
        self.model.conf = Config.YOLO_CONFIDENCE
        self.model.overrides['imgsz'] = Config.YOLO_IMG_SIZE
        self.model.overrides['verbose'] = False
    
    def detect(self, image: np.ndarray) -> List[DetectedObject]:
        """Detect objects in image and return their centers"""
        all_classes = list(TARGET_CLASS_NAMES.keys())
        results = self.model(image, classes=all_classes)
        boxes = results[0].boxes
        
        detected_objects = []
        for box in boxes:
            cls_id = int(box.cls[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            x_center = (x1 + x2) // 2
            y_center = (y1 + y2) // 2
            
            class_name = TARGET_CLASS_NAMES.get(cls_id, "unknown")
            detected_objects.append(
                DetectedObject(class_name, x_center, y_center)
            )
        
        return detected_objects