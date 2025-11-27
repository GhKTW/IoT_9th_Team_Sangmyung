"""
Configuration and constants for the robot system
"""
from enum import Enum


class Config:
    """Central configuration class"""
    # Camera settings
    CAMERA_INDEX = 0
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 640
    FRAME_RATE = 30
    PROCESS_EVERY_N_FRAMES = 15
    
    # YOLO settings
    YOLO_MODEL = 'yolov8n.pt'
    YOLO_CONFIDENCE = 0.4
    YOLO_IMG_SIZE = 640
    
    # Movement settings
    DEFAULT_SPEED = 0.6
    TURN_SPEED_RATIO = 0.7
    
    # Tracking settings
    DEAD_ZONE = 50  # pixels from center
    OBJECT_ALIGNMENT_THRESHOLD = 50  # pixels
    
    # Lifting settings
    MAX_LIFT_ATTEMPTS = 30
    MAX_WEIGHT_THRESHOLD = 55000
    DISTANCE_THRESHOLD = 8  # cm
    
    # Buffer settings
    MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB


class ObjectClass(Enum):
    """Target object classes"""
    APPLE = 47
    BANANA = 46
    BROCCOLI = 50
    TRUCK = 7


# Class name mappings
TARGET_CLASS_NAMES = {
    ObjectClass.APPLE.value: "apple",
    ObjectClass.BANANA.value: "banana",
    ObjectClass.BROCCOLI.value: "broccoli",
    ObjectClass.TRUCK.value: "truck"
}

TRUCK_CLASS_NAMES = {
    ObjectClass.TRUCK.value: "truck"
}