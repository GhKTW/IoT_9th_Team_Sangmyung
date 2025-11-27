"""
Main robot controller and entry point
"""
import threading

from sensors import init_spi, setup_loadcell, read_weights
from config import Config, ObjectClass, TARGET_CLASS_NAMES
from models import RobotState
from detection import ObjectDetector
from camera import CameraManager
from movement import MovementController, LineFollower
from tracking import ObjectTracker
from lifting import LiftingController
from light_control import LightController
from line_monitor import LineMonitor


def initialize_hardware():
    """Initialize all hardware components"""
    init_spi()
    setup_loadcell()
    for _ in range(5):
        weight = read_weights()


class RobotController:
    """Main robot control logic"""
    
    def __init__(self):
        self.robot_state = RobotState()
        self.movement = MovementController(self.robot_state)
        self.line_follower = LineFollower()
        self.line_monitor = LineMonitor(self.robot_state, check_interval=0.02)  # 20ms for high accuracy
        self.lifting = LiftingController(self.movement, self.line_follower, self.line_monitor)
        self.tracker = ObjectTracker(self.movement, self.robot_state, self.line_monitor)
        self.detector = ObjectDetector()
        self.camera = CameraManager(self.detector, self.robot_state)
        self.light_controller = LightController(self.robot_state, threshold=10, check_interval=0.5)

    def start(self):
        """Start robot operation"""
        initialize_hardware()
        
        # Start light monitoring thread
        self.light_controller.start_monitoring()
        
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
        failure_count = {}  # Track failures per target
        max_failures_per_target = 3  # Skip target after 3 consecutive failures
        
        # Initialize failure counters
        for target in target_sequence:
            failure_count[target] = 0
        
        try:
            while not self.robot_state.exit_flag:
                target_id = target_sequence[current_idx]
                target_name = TARGET_CLASS_NAMES[target_id.value]
                
                # Check if this target should be skipped
                if failure_count[target_id] >= max_failures_per_target:
                    print(f"\n⚠️ Skipping {target_name} (failed {failure_count[target_id]} times)")
                    current_idx = (current_idx + 1) % len(target_sequence)
                    
                    # Reset failure count when cycling back
                    if current_idx == 0:
                        print("Resetting failure counts for new cycle")
                        for target in target_sequence:
                            failure_count[target] = 0
                    continue
                
                print(f"\n=== Processing target: {target_name} (attempt {failure_count[target_id] + 1}/{max_failures_per_target}) ===")
                
                # Navigate to object and pick it up
                pickup_success = False
                if self.tracker.track_to_target(target_name, is_pickup=True):
                    if self.lifting.attempt_pickup():
                        pickup_success = True
                
                if not pickup_success:
                    print(f"❌ Failed to pickup {target_name}")
                    failure_count[target_id] += 1
                    continue
                
                # Navigate to destination and place object
                place_success = False
                if self.tracker.track_to_target(target_name, is_pickup=False):
                    if self.lifting.attempt_place():
                        place_success = True
                
                if not place_success:
                    print(f"❌ Failed to place {target_name}")
                    failure_count[target_id] += 1
                    continue
                
                # Success - reset failure count and move to next target
                print(f"✅ Successfully completed {target_name}")
                failure_count[target_id] = 0
                current_idx = (current_idx + 1) % len(target_sequence)
                
        except KeyboardInterrupt:
            print("\nMission terminated by user")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        print("Cleaning up...")
        self.robot_state.exit_flag = True
        self.movement.stop()
        
        # Stop light controller
        self.light_controller.stop()
        
        # Terminate camera process
        if self.robot_state.camera_process:
            self.robot_state.camera_process.terminate()
            self.robot_state.camera_process.wait(timeout=2)
        
        # Clean up GPIO resources
        try:
            from gpiozero import Device
            Device.pin_factory.reset()
            print("GPIO resources cleaned")
        except Exception as e:
            print(f"GPIO cleanup error: {e}")


if __name__ == "__main__":
    robot = RobotController()
    robot.start()