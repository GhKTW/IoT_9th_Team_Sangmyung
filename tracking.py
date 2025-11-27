"""
Object tracking and navigation
"""
import time
from typing import List, Optional

from sensors import get_distance_values
from config import Config
from models import DetectedObject, RobotState
from movement import MovementController
from line_monitor import LineMonitor


class ObjectTracker:
    """Handles object tracking and navigation"""
    
    def __init__(self, movement: MovementController, robot_state: RobotState, line_monitor: LineMonitor):
        self.movement = movement
        self.robot_state = robot_state
        self.line_monitor = line_monitor
        self.last_processed_sequence = 0
        self.collision_threshold = 12  # cm
        self.last_seen_direction = 0  # -1: left, 0: center, 1: right
    
    def track_to_target(self, target_class: str, is_pickup: bool, max_time: float = 60.0) -> bool:
        """
        Track and navigate to target object
        
        Args:
            target_class: Name of target object class
            is_pickup: True for pickup mode, False for place mode
            max_time: Maximum time to search in seconds
        
        Returns:
            True if navigation successful
        """
        print(f"{'Pickup' if is_pickup else 'Place'} mode started for {target_class}")
        
        start_time = time.time()
        detected_once = False
        lost_detection_count = 0
        max_lost_count = 10  # Number of detection cycles before attempting recovery
        
        while not self.robot_state.exit_flag:
            # ALWAYS check line detection first (pickup mode)
            if is_pickup and self.line_monitor.is_line_detected():
                print("✓ Line detected - object is right in front! Stopping for pickup...")
                self.movement.stop()
                return True
            
            # Check timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > max_time:
                print(f"Tracking timeout after {max_time}s - target not reached")
                self.movement.stop()
                return False
            
            # # Check front distance for collision avoidance
            # distance_values = get_distance_values()
            # front_distance = distance_values[2]  # Right/front sensor
            # 
            # if front_distance <= self.collision_threshold:
            #     print(f"Obstacle detected at {front_distance}cm - initiating recovery")
            #     self.movement.stop()
            #     
            #     # Attempt recovery from collision
            #     if self._attempt_collision_recovery():
            #         print("Collision recovery successful - resuming from search mode")
            #         detected_once = False  # Reset to search mode
            #         lost_detection_count = 0
            #         continue
            #     else:
            #         print("Collision recovery failed - stopping")
            #         self.movement.stop()
            #         return False
            
            # Get detection result
            detection = self.robot_state.get_detection()
            
            # Wait if no new detection results
            if detection is None or detection.sequence_num <= self.last_processed_sequence:
                time.sleep(0.01)
                continue
            
            # Check line again before processing detection
            if is_pickup and self.line_monitor.is_line_detected():
                print("✓ Line detected - stopping for pickup...")
                self.movement.stop()
                return True
            
            # Process new detection result
            self.last_processed_sequence = detection.sequence_num
            centers = detection.objects
            
            # Find target object
            target_obj = self._find_target(centers, target_class, is_pickup)
            
            if target_obj is None:
                if not detected_once:
                    # Check line before searching
                    if is_pickup and self.line_monitor.is_line_detected():
                        print("✓ Line detected during search - stopping for pickup...")
                        self.movement.stop()
                        return True
                    
                    # Initial search - haven't found target yet
                    print(f"Target not found (detection #{detection.sequence_num}) - searching...")
                    self.movement.turn_left(0.5, 1)
                    time.sleep(0.3)
                    continue
                
                # Lost detection after finding it once
                print(f"Lost detection (detection #{detection.sequence_num})")
                
                # Count consecutive losses for recovery decision
                lost_detection_count += 1
                print(f"Lost detection count: {lost_detection_count}/{max_lost_count}")
                
                if lost_detection_count >= max_lost_count:
                    # Check line before attempting recovery
                    if is_pickup and self.line_monitor.is_line_detected():
                        print("✓ Line detected before recovery - stopping for pickup...")
                        self.movement.stop()
                        return True
                    
                    # Attempt recovery
                    print("Detection lost too many times - attempting recovery...")
                    if self._attempt_recovery():
                        print("Recovery successful - resuming tracking")
                        lost_detection_count = 0
                        detected_once = False  # Reset to search mode
                        continue
                    else:
                        print("Recovery failed - stopping")
                        self.movement.stop()
                        return False
                
                continue
            
            # Target found - reset counters
            detected_once = True
            lost_detection_count = 0
            
            # Update last seen direction for recovery
            error = target_obj.x_center - (Config.FRAME_WIDTH // 2)
            if error < -Config.DEAD_ZONE:
                self.last_seen_direction = 1  # Target on right
            elif error > Config.DEAD_ZONE:
                self.last_seen_direction = -1  # Target on left
            else:
                self.last_seen_direction = 0  # Target centered
            
            # Calculate steering based on target position
            error = target_obj.x_center - (Config.FRAME_WIDTH // 2)
            
            # Check line before any movement
            if is_pickup and self.line_monitor.is_line_detected():
                print("✓ Line detected before movement - stopping for pickup...")
                self.movement.stop()
                return True
            
            # Move towards target
            if abs(error) <= Config.DEAD_ZONE:
                print(f"Target centered (detection #{detection.sequence_num}) - moving forward")
                self.movement.forward(0.4, 1)
                time.sleep(0.3)
            elif error < 0:
                print(f"Target on right (detection #{detection.sequence_num}) - turning right")
                self.movement.turn_right(0.4, 1)
            else:
                print(f"Target on left (detection #{detection.sequence_num}) - turning left")
                self.movement.turn_left(0.4, 1)
            
            # Check if reached line (destination) - for place mode
            if not is_pickup and self.line_monitor.is_line_detected():
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
            # Pickup mode: ignore target if it's near a truck
            if target_obj is None:
                return None
            
            truck_obj = next((obj for obj in centers if obj.class_name == "truck"), None)
            
            # If truck exists and target is aligned with truck, ignore this target
            if truck_obj is not None:
                if abs(target_obj.x_center - truck_obj.x_center) <= Config.OBJECT_ALIGNMENT_THRESHOLD:
                    print(f"Target {target_class} is near truck - ignoring (aligned)")
                    return None
            
            return target_obj
        
        # Place mode: need both target and truck
        truck_obj = next((obj for obj in centers if obj.class_name == "truck"), None)
        
        if target_obj is None or truck_obj is None:
            return None
        
        # Check if objects are aligned
        if abs(target_obj.x_center - truck_obj.x_center) > Config.OBJECT_ALIGNMENT_THRESHOLD:
            return None
        
        return truck_obj
    
    def _approach_using_distance(self, target_distance: float = 4.0, max_attempts: int = 15) -> bool:
        """
        Use distance sensor to approach object when vision is lost
        
        Args:
            target_distance: Target distance in cm
            max_attempts: Maximum forward movements
        
        Returns:
            True if reached target distance
        """
        print(f"Approaching using distance sensor (target: {target_distance}cm)...")
        
        for attempt in range(max_attempts):
            distance_values = get_distance_values()
            center_distance = distance_values[1]  # Center sensor
            
            print(f"  Attempt {attempt + 1}/{max_attempts}: distance = {center_distance}cm")
            
            # Reached target distance
            if center_distance <= target_distance:
                print(f"  ✓ Target distance reached ({center_distance}cm)")
                self.movement.stop()
                return True
            
            # Too far - continue forward
            if center_distance > target_distance + 2:
                self.movement.forward(0.1, 1)  # Small forward movement
                time.sleep(0.1)
            else:
                # Close enough - fine adjustment
                self.movement.forward(0.05, 1)
                time.sleep(0.1)
        
        print(f"  ✗ Failed to reach target distance after {max_attempts} attempts")
        return False
    
    def _attempt_collision_recovery(self) -> bool:
        """
        Attempt to recover from collision/obstacle detection
        
        Returns:
            True if recovery successful (ready to search for object again)
        """
        print("Starting collision recovery procedure...")
        
        # Step 1: Back up from obstacle
        print("Step 1: Backing up from obstacle...")
        self.movement.backward(0.8, 1)  # Back up longer than detection loss recovery
        time.sleep(0.8)
        self.movement.stop()
        
        # Step 2: Rotate and search for object
        print("Step 2: Rotating to search for object...")
        search_attempts = 12  # 12 x 30° = 360°
        rotation_duration = 0.25
        
        for attempt in range(search_attempts):
            print(f"Search rotation {attempt + 1}/{search_attempts}")
            
            # Rotate
            self.movement.turn_left(rotation_duration, 1)
            time.sleep(0.2)
            
            # Wait for new detection
            time.sleep(0.3)
            
            # Check if any objects are found
            detection = self.robot_state.get_detection()
            if detection is not None and len(detection.objects) > 0:
                print(f"Found {len(detection.objects)} object(s) during collision recovery")
                
                # Check front distance is now clear
                distance_values = get_distance_values()
                front_distance = distance_values[2]
                
                if front_distance > self.collision_threshold:
                    print(f"Path clear (distance: {front_distance}cm)")
                    return True
                else:
                    print(f"Still too close (distance: {front_distance}cm), continuing search...")
        
        print("Collision recovery failed - no clear path found")
        return False
    
    def _attempt_recovery(self) -> bool:
        """
        Attempt to recover from lost detection using progressive search strategy
        
        Returns:
            True if recovery successful (object found again)
        """
        print("Starting recovery procedure...")
        
        # Step 1: Back up
        print("Step 1: Backing up...")
        self.movement.backward(0.5, 1)
        time.sleep(0.5)
        self.movement.stop()
        
        # Step 2: Progressive search based on last seen direction
        # Stage 1: Quick search in last seen direction (±60°)
        print(f"Stage 1: Searching near last seen direction ({self.last_seen_direction})...")
        if self._search_in_range(attempts=2, duration=0.25, prefer_direction=self.last_seen_direction):
            return True
        
        # Stage 2: Medium search (±120°)
        print("Stage 2: Expanding search to ±120°...")
        if self._search_in_range(attempts=4, duration=0.25, prefer_direction=self.last_seen_direction):
            return True
        
        # Stage 3: Full 360° search as last resort
        print("Stage 3: Full 360° search as last resort...")
        if self._search_in_range(attempts=8, duration=0.3, prefer_direction=0):
            return True
        
        print("Recovery failed - no objects detected after all stages")
        return False
    
    def _search_in_range(self, attempts: int, duration: float, prefer_direction: int) -> bool:
        """
        Search for objects by rotating
        
        Args:
            attempts: Number of rotation steps
            duration: Duration for each rotation
            prefer_direction: -1 for left first, 1 for right first, 0 for left only
        
        Returns:
            True if object found
        """
        # Determine rotation direction based on preference
        if prefer_direction == 1:
            # Search right first
            rotation_func = self.movement.turn_right
            direction_name = "right"
        else:
            # Search left (default for center and left)
            rotation_func = self.movement.turn_left
            direction_name = "left"
        
        for attempt in range(attempts):
            print(f"  Rotating {direction_name} ({attempt + 1}/{attempts})...")
            
            # Rotate
            rotation_func(duration, 1)
            time.sleep(0.2)
            
            # Wait for new detection
            time.sleep(0.3)
            
            # Check if target is found
            detection = self.robot_state.get_detection()
            if detection is not None and len(detection.objects) > 0:
                print(f"  ✓ Found {len(detection.objects)} object(s)!")
                return True
        
        return False