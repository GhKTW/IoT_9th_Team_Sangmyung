"""
Data models and structures for the robot system
"""
from dataclasses import dataclass
from typing import List, Optional
import threading
import subprocess


@dataclass
class DetectedObject:
    """Represents a detected object"""
    class_name: str
    x_center: int
    y_center: int


@dataclass
class DetectionResult:
    """Represents detection result with sequence number"""
    objects: List[DetectedObject]
    sequence_num: int


class RobotState:
    """Manages global robot state"""
    def __init__(self):
        self.exit_flag = False
        self.current_speed = 0.6
        self.tracking_enabled = True
        self.latest_detection: Optional[DetectionResult] = None
        self.detection_lock = threading.Lock()
        self.frame_idx = 0
        self.detection_sequence = 0
        self.camera_process: Optional[subprocess.Popen] = None
    
    def update_detection(self, objects: List[DetectedObject]):
        """Thread-safe update of detected objects with sequence number"""
        with self.detection_lock:
            self.detection_sequence += 1
            self.latest_detection = DetectionResult(
                objects=objects[:],
                sequence_num=self.detection_sequence
            )
    
    def get_detection(self) -> Optional[DetectionResult]:
        """Thread-safe retrieval of latest detection"""
        with self.detection_lock:
            return self.latest_detection