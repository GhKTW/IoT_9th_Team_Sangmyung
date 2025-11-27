import cv2
import subprocess
import shlex
import numpy as np
import threading
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum
from ultralytics import YOLO
from sensors import *


# ========================================
# Configuration & Constants
# ========================================
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
    DISTANCE_THRESHOLD =  8 # cm
    
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


# ========================================
# Global State Management
# ========================================
class RobotState:
    """Manages global robot state"""
    def __init__(self):
        self.exit_flag = False
        self.current_speed = Config.DEFAULT_SPEED
        self.tracking_enabled = True
        self.latest_detection: Optional[DetectionResult] = None
        self.detection_lock = threading.Lock()
        self.frame_idx = 0
        self.detection_sequence = 0  # 검출 순서 카운터
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


# Global state instance
robot_state = RobotState()


# ========================================
# Hardware Initialization
# ========================================
def initialize_hardware():
    """Initialize all hardware components"""
    init_spi()
    setup_loadcell()
    for _ in range(5):
        weight = read_weights()


# ========================================
# YOLO Detection
# ========================================
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


# ========================================
# Camera Management
# ========================================
class CameraManager:
    """Manages camera capture and processing"""
    
    def __init__(self, detector: ObjectDetector):
        self.detector = detector
    
    def start_capture(self):
        """Start camera capture process"""
        cmd = (
            f'libcamera-vid --inline --vflip --nopreview -t 0 --codec mjpeg '
            f'--width {Config.FRAME_WIDTH} --height {Config.FRAME_HEIGHT} '
            f'--framerate {Config.FRAME_RATE} -o - --camera {Config.CAMERA_INDEX}'
        )
        robot_state.camera_process = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
    
    def read_frames_loop(self):
        """Main frame reading loop (runs in thread)"""
        buffer = b''
        
        while not robot_state.exit_flag:
            if robot_state.camera_process is None:
                continue
            
            chunk = robot_state.camera_process.stdout.read(4096)
            if not chunk:
                continue
            
            buffer += chunk
            
            # Process complete JPEG frames
            while True:
                start = buffer.find(b'\xff\xd8')
                end = buffer.find(b'\xff\xd9')
                
                if start != -1 and end != -1 and end > start:
                    jpg = buffer[start:end + 2]
                    buffer = buffer[end + 2:]
                    
                    image = cv2.imdecode(
                        np.frombuffer(jpg, np.uint8),
                        cv2.IMREAD_COLOR
                    )
                    
                    if image is not None:
                        self._process_frame(image)
                else:
                    break
            
            # Prevent buffer overflow
            if len(buffer) > Config.MAX_BUFFER_SIZE:
                buffer = b''
    
    def _process_frame(self, image: np.ndarray):
        """Process a single frame"""
        robot_state.frame_idx += 1
        
        if robot_state.frame_idx % Config.PROCESS_EVERY_N_FRAMES == 0:
            objects = self.detector.detect(image)
            robot_state.update_detection(objects)
            print(f"Detection #{robot_state.detection_sequence}: {[(obj.class_name, obj.x_center) for obj in objects]}")


# ========================================
# Movement Control
# ========================================
class MovementController:
    """Controls robot movement"""
    
    @staticmethod
    def set_speed(value: float):
        """Set movement speed (0.0 to 1.0)"""
        robot_state.current_speed = max(0.0, min(1.0, value))
    
    @staticmethod
    def stop():
        """Stop all motors"""
        stop_all()
    
    @staticmethod
    def brake():
        """Apply brake"""
        brake_all()
    
    @staticmethod
    def forward(duration: Optional[float] = None, speed: Optional[float] = None):
        """Move forward"""
        speed = speed or robot_state.current_speed
        leftMotorForward(speed)
        rightMotorForward(speed)
        if duration:
            time.sleep(duration)
            stop_all()
    
    @staticmethod
    def backward(duration: Optional[float] = None, speed: Optional[float] = None):
        """Move backward"""
        speed = speed or robot_state.current_speed
        leftMotorBackward(speed)
        rightMotorBackward(speed)
        if duration:
            time.sleep(duration)
            stop_all()
    
    @staticmethod
    def turn_left(duration: Optional[float] = None, speed: Optional[float] = None):
        """Turn left"""
        speed = speed or (robot_state.current_speed * Config.TURN_SPEED_RATIO)
        leftMotorBackward(speed)
        rightMotorForward(speed)
        if duration:
            time.sleep(duration)
            stop_all()
    
    @staticmethod
    def turn_right(duration: Optional[float] = None, speed: Optional[float] = None):
        """Turn right"""
        speed = speed or (robot_state.current_speed * Config.TURN_SPEED_RATIO)
        leftMotorForward(speed)
        rightMotorBackward(speed)
        if duration:
            time.sleep(duration)
            stop_all()


# ========================================
# Line Following
# ========================================
class LineFollower:
    """Handles line following behavior"""
    
    @staticmethod
    def follow_to_target(movement: MovementController) -> bool:
        """Follow line until reaching target (all sensors detect line)"""
        while True:
            line_values = get_line_values()
            left, center, right = line_values[0], line_values[1], line_values[2]

            if (left == 1 or center == 1 or right == 1):
                movement.stop()
                return True


# ========================================
# Object Tracking
# ========================================
class ObjectTracker:
    """Handles object tracking and navigation"""
    
    def __init__(self, movement: MovementController):
        self.movement = movement
        self.last_processed_sequence = 0  # 마지막으로 처리한 검출 순서
    
    def track_to_target(self, target_class: str, is_pickup: bool) -> bool:
        """
        Track and navigate to target object
        
        Args:
            target_class: Name of target object class
            is_pickup: True for pickup mode, False for place mode
        
        Returns:
            True if navigation successful
        """
        print(f"{'Pickup' if is_pickup else 'Place'} mode started for {target_class}")
        
        detected_once = False
        
        while not robot_state.exit_flag:
            detection = robot_state.get_detection()
            line_values = get_line_values()
            
            # 새로운 검출 결과가 없으면 대기
            if detection is None or detection.sequence_num <= self.last_processed_sequence:
                time.sleep(0.01)  # CPU 과부하 방지
                continue
            
            # 새로운 검출 결과 처리
            self.last_processed_sequence = detection.sequence_num
            centers = detection.objects
            
            # Find target object
            target_obj = self._find_target(centers, target_class, is_pickup)
            
            if target_obj is None:
                if detected_once:
                    continue
                print(f"Target not found (detection #{detection.sequence_num}) - searching...")
                self.movement.turn_left(0.2, 0.5)
                time.sleep(0.3)
                continue
            
            detected_once = True
            
            # Calculate steering based on target position
            error = target_obj.x_center - (Config.FRAME_WIDTH // 2)
            
            # Move towards target (새 검출 결과에 대해서만 실행)
            if abs(error) <= Config.DEAD_ZONE:
                print(f"Target centered (detection #{detection.sequence_num}) - moving forward")
                self.movement.forward(0.1, 0.5)
            elif error < 0:
                print(f"Target on right (detection #{detection.sequence_num}) - turning right")
                self.movement.turn_right(0.05, 0.5)
            else:
                print(f"Target on left (detection #{detection.sequence_num}) - turning left")
                self.movement.turn_left(0.05, 0.5)
            
            # Check if reached line (destination)
            if any(v == 1 for v in line_values):
                print("Line detected - destination reached")
                self.movement.stop()
                return True
        
        return False
    
    def _find_target(
        self,
        centers: List[DetectedObject],
        target_class: str,
        is_pickup: bool
    ) -> Optional[DetectedObject]:
        """Find appropriate target based on mode"""
        target_obj = next((obj for obj in centers if obj.class_name == target_class), None)
        
        if is_pickup:
            return target_obj
        
        # Place mode: need both target and truck
        truck_obj = next((obj for obj in centers if obj.class_name == "truck"), None)
        
        if target_obj is None or truck_obj is None:
            return None
        
        # Check if objects are aligned
        if abs(target_obj.x_center - truck_obj.x_center) > Config.OBJECT_ALIGNMENT_THRESHOLD:
            return None
        
        return truck_obj  # Use truck position for placing


# ========================================
# Lifting Operations
# ========================================
class LiftingController:
    """Handles object lifting and placing"""
    
    def __init__(self, movement: MovementController, line_follower: LineFollower):
        self.movement = movement
        self.line_follower = line_follower
    
    def attempt_pickup(self) -> bool:
        """Attempt to pick up object"""
        print("Starting pickup attempt")
        
        # Follow line to object
        self.line_follower.follow_to_target(self.movement)
        
        # Check if object is in range
        if not self._is_object_in_range():
            print("Object not in pickup range")
            self._return_to_path()
            return False
        
        # Attempt lift
        if not self._lift_object():
            print("Lift failed - object too heavy")
            self._return_to_path()
            return False
        
        print("Pickup successful")
        self._return_to_path()
        return True
    
    def attempt_place(self) -> bool:
        """Attempt to place object"""
        print("Starting place attempt")
        
        # Follow line to destination
        self.line_follower.follow_to_target(self.movement)
        
        # Lower object
        for i in range(20): 
            lift_motor_down(0.1, 0.5)  # 속도 0.5로 들기
            weight = read_weights()
            total_weight = weight[0] + weight[1]
            print(total_weight)
            if total_weight <= 5000:  # 총 무게가 기준치 이하면 계속 들기
                break
        print("Object placed")
        
        self._return_to_path()
        self.movement.stop()
        return True
    
    def _is_object_in_range(self) -> bool:
        """Check if object is within pickup range"""
        for _ in range(20):
            center_distance = get_distance_values()[1]
            if center_distance <= Config.DISTANCE_THRESHOLD:
                return True
            self.movement.forward(0.05, 0.5)
            time.sleep(0.2)
        return False
    
    def _lift_object(self) -> bool:
        """Lift object and check weight"""
        for iteration in range(Config.MAX_LIFT_ATTEMPTS):
            lift_motor_up(0.1, 0.5)
            
            weight = read_weights()
            total_weight = sum(weight)
            
            if total_weight >= Config.MAX_WEIGHT_THRESHOLD:
                print(f"Weight limit exceeded: {total_weight}")
                self.attempt_place()
                return False
        
        print("Lift successful")
        self.movement.stop()
        return True
    
    def _return_to_path(self):
        """Return to path after pickup/place operation"""
        print("Returning to path")
        self.movement.backward(0.5, 0.5)
        self.movement.turn_right(2.18)  # ~180 degrees


# ========================================
# Main Robot Controller
# ========================================
class RobotController:
    """Main robot control logic"""
    
    def __init__(self):
        self.movement = MovementController()
        self.line_follower = LineFollower()
        self.lifting = LiftingController(self.movement, self.line_follower)
        self.tracker = ObjectTracker(self.movement)
        self.detector = ObjectDetector()
        self.camera = CameraManager(self.detector)
    
    def start(self):
        """Start robot operation"""
        initialize_hardware()
        
        # Start camera thread
        self.camera.start_capture()
        camera_thread = threading.Thread(
            target=self.camera.read_frames_loop,
            daemon=True
        )
        camera_thread.start()
        
        # Main operation loop
        self.run_mission()
    
    def run_mission(self):
        """Execute main mission"""
        target_sequence = [
            ObjectClass.APPLE,
            ObjectClass.BANANA,
            ObjectClass.BROCCOLI
        ]
        
        current_idx = 0
        
        try:
            while not robot_state.exit_flag:
                target_id = target_sequence[current_idx]
                target_name = TARGET_CLASS_NAMES[target_id.value]
                
                print(f"\n=== Processing target: {target_name} ===")
                
                # Navigate to object and pick it up
                if self.tracker.track_to_target(target_name, is_pickup=True):
                    if self.lifting.attempt_pickup():
                        # Navigate to destination and place object
                        self.tracker.track_to_target(target_name, is_pickup=False)
                        self.lifting.attempt_place()
                
                # Move to next target
                current_idx = (current_idx + 1) % len(target_sequence)
                
        except KeyboardInterrupt:
            print("\nMission terminated by user")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        print("Cleaning up...")
        robot_state.exit_flag = True
        self.movement.stop()
        
        # Terminate camera process
        if robot_state.camera_process:
            robot_state.camera_process.terminate()
            robot_state.camera_process.wait(timeout=2)
        
        # Clean up GPIO resources
        try:
            from gpiozero import Device
            Device.pin_factory.reset()
            print("GPIO resources cleaned")
        except Exception as e:
            print(f"GPIO cleanup error: {e}")


# ========================================
# Entry Point
# ========================================
if __name__ == "__main__":
    robot = RobotController()
    robot.start()