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
    FRAME_WIDTH = 320
    FRAME_HEIGHT = 320
    FRAME_RATE = 30
    PROCESS_EVERY_N_FRAMES = 15
    
    # YOLO settings
    YOLO_MODEL = 'yolov8n.pt'
    YOLO_CONFIDENCE = 0.4
    YOLO_IMG_SIZE = 320
    
    # Movement settings
    DEFAULT_SPEED = 0.6
    TURN_SPEED_RATIO = 0.7
    
    # Tracking settings
    DEAD_ZONE = 20  # pixels from center
    OBJECT_ALIGNMENT_THRESHOLD = 50  # pixels
    
    # Lifting settings
    MAX_LIFT_ATTEMPTS = 15
    MAX_WEIGHT_THRESHOLD = 55000
    DISTANCE_THRESHOLD = 10  # cm
    
    # Buffer settings
    MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB


class ObjectClass(Enum):
    """Target object classes"""
    APPLE = 47
    BANANA = 46
    ORANGE = 49
    TRUCK = 7


# Class name mappings
TARGET_CLASS_NAMES = {
    ObjectClass.APPLE.value: "apple",
    ObjectClass.BANANA.value: "banana",
    ObjectClass.ORANGE.value: "orange",
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


# ========================================
# Global State Management
# ========================================
class RobotState:
    """Manages global robot state"""
    def __init__(self):
        self.exit_flag = False
        self.current_speed = Config.DEFAULT_SPEED
        self.tracking_enabled = True
        self.latest_centers: List[DetectedObject] = []
        self.centers_lock = threading.Lock()
        self.frame_idx = 0
        self.camera_process: Optional[subprocess.Popen] = None
    
    def update_centers(self, centers: List[DetectedObject]):
        """Thread-safe update of detected centers"""
        with self.centers_lock:
            self.latest_centers = centers[:]
    
    def get_centers(self) -> List[DetectedObject]:
        """Thread-safe retrieval of detected centers"""
        with self.centers_lock:
            return self.latest_centers[:]


# Global state instance
robot_state = RobotState()


# ========================================
# Hardware Initialization
# ========================================
def initialize_hardware():
    """Initialize all hardware components"""
    init_spi()
    setup_loadcell()


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
            centers = self.detector.detect(image)
            robot_state.update_centers(centers)
            print(f"Detected: {[(obj.class_name, obj.x_center) for obj in centers]}")


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
            
            # 0 0 0: No line detected / 0 1 0: Center only - move forward
            if (left == 0 and center == 0 and right == 0) or (left == 0 and center == 1 and right == 0):
                movement.forward(0.1, 0.5)
            
            # 1 0 0: Left sensor only / 1 1 0: Left and center - turn left
            elif (left == 1 and center == 0 and right == 0) or (left == 1 and center == 1 and right == 0):
                movement.turn_left(0.1, 0.5)
            
            # 0 0 1: Right sensor only / 0 1 1: Center and right - turn right
            elif (left == 0 and center == 0 and right == 1) or (left == 0 and center == 1 and right == 1):
                movement.turn_right(0.1, 0.5)
            
            # 1 1 1: All sensors detect line - arrived at target
            elif left == 1 and center == 1 and right == 1:
                print("Line fully detected - arrived at target")
                movement.stop()
                return True
            
            # 1 0 1: Left and right (shouldn't happen normally, treat as forward)
            else:
                movement.forward(0.1, 0.5)


# ========================================
# Object Tracking
# ========================================
class ObjectTracker:
    """Handles object tracking and navigation"""
    
    def __init__(self, movement: MovementController):
        self.movement = movement
    
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
        
        while not robot_state.exit_flag:
            centers = robot_state.get_centers()
            line_values = get_line_values()
            
            # Find target object
            target_obj = self._find_target(centers, target_class, is_pickup)
            
            if target_obj is None:
                print("Target not found - searching...")
                self.movement.turn_left(0.2, 0.5)
                time.sleep(0.3)
                continue
            
            # Calculate steering based on target position
            error = target_obj.x_center - (Config.FRAME_WIDTH // 2)
            
            # Move towards target
            if abs(error) <= Config.DEAD_ZONE:
                print("Target centered - moving forward")
                self.movement.forward(0.5, 0.5)
            elif error < 0:
                print("Target on left - turning right")
                self.movement.turn_right(0.2, 0.5)
            else:
                print("Target on right - turning left")
                self.movement.turn_left(0.2, 0.5)
            
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
        lift_motor_down(Config.MAX_LIFT_ATTEMPTS, 0.5)
        print("Object placed")
        
        self._return_to_path()
        return True
    
    def _is_object_in_range(self) -> bool:
        """Check if object is within pickup range"""
        for _ in range(10):
            center_distance = get_distance_values()[1]
            if center_distance <= Config.DISTANCE_THRESHOLD:
                return True
            self.movement.forward(0.2, 0.5)
        return False
    
    def _lift_object(self) -> bool:
        """Lift object and check weight"""
        for iteration in range(Config.MAX_LIFT_ATTEMPTS):
            lift_motor_up(0.1, 0.5)
            
            weight = read_weights()
            total_weight = sum(weight)
            
            if total_weight >= Config.MAX_WEIGHT_THRESHOLD:
                print(f"Weight limit exceeded: {total_weight}")
                lift_motor_down(iteration, 0.5)
                return False
        
        print("Lift successful")
        return True
    
    def _return_to_path(self):
        """Return to path after pickup/place operation"""
        print("Returning to path")
        self.movement.backward(1.0)
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
            ObjectClass.ORANGE
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