"""
Object lifting and placing operations
"""
import time

from sensors import *
from config import Config
from movement import MovementController, LineFollower
from line_monitor import LineMonitor


class LiftingController:
    """Handles object lifting and placing"""
    
    def __init__(self, movement: MovementController, line_follower: LineFollower, line_monitor: LineMonitor):
        self.movement = movement
        self.line_follower = line_follower
        self.line_monitor = line_monitor
    
    def attempt_pickup(self) -> bool:
        """Attempt to pick up object"""
        print("Starting pickup attempt")
        
        # Line already detected by tracking - just stop briefly
        self.movement.stop()
        time.sleep(0.2)
        
        # Record initial weight
        initial_weight = read_weights()
        initial_total = sum(initial_weight)
        print(f"Initial weight: {initial_total}")
        
        # Check if object is in range
        if not self._is_object_in_range():
            print("Object not in pickup range")
            self._return_to_path()
            return False
        
        # Attempt lift
        if not self._lift_object():
            print("Lift failed")
            self._return_to_path()
            return False
        
        # Verify object was actually picked up by checking weight increase
        time.sleep(0.3)  # Wait for weight to stabilize
        final_weight = read_weights()
        final_total = sum(final_weight)
        weight_increase = final_total - initial_total
        
        print(f"Final weight: {final_total}, Increase: {weight_increase}")
        
        if weight_increase < 1000:  # Minimum 1kg increase expected
            print(f"Warning: Weight increase too small ({weight_increase}), object may not be lifted")
            # Try one more time
            print("Attempting lift again...")
            if not self._lift_object():
                print("Second lift attempt failed")
                self._return_to_path()
                return False
            
            # Check weight again
            final_weight = read_weights()
            final_total = sum(final_weight)
            weight_increase = final_total - initial_total
            
            if weight_increase < 1000:
                print(f"Still no significant weight increase - aborting")
                self._return_to_path()
                return False
        
        print(f"Pickup successful - weight increased by {weight_increase}")
        self._return_to_path()
        
        return True
    
    def attempt_place(self) -> bool:
        """Attempt to place object"""
        print("Starting place attempt")
        
        # Follow line to destination
        if not self.line_follower.follow_to_target(self.movement):
            print("Failed to find destination line - aborting place")
            self._return_to_path()
            return False
        
        # Lower object
        for i in range(20): 
            lift_motor_down(0.1, 1)
            weight = read_weights()
            total_weight = weight[0] + weight[1]
            print(total_weight)
            if total_weight <= 5000:
                break
        print("Object placed")
        
        self._return_to_path()
        self.movement.stop()
        return True
    
    def _is_object_in_range(self) -> bool:
        """Check if object is within pickup range and move closer if needed"""
        print("Checking object distance...")
        
        max_retries = 2  # Number of times to retry with adjustment
        
        for retry in range(max_retries + 1):
            if retry > 0:
                print(f"Retry {retry}/{max_retries}: Adjusting position...")
                # Back up and adjust laterally
                self.movement.backward(0.3, 1)
                time.sleep(0.2)
                
                # Alternate left/right adjustment
                if retry % 2 == 1:
                    self.movement.turn_left(0.15, 1)
                else:
                    self.movement.turn_right(0.15, 1)
                time.sleep(0.2)
            
            # Try to approach object
            for attempt in range(20):
                distance_values = get_distance_values()
                center_distance = distance_values[1]
                
                print(f"Distance check {attempt + 1}: center distance = {center_distance} cm")
                
                # Object is in pickup range when distance <= 4cm
                if center_distance <= 4:
                    print(f"Object in range (distance: {center_distance} cm)")
                    self.movement.stop()
                    return True
                
                # Move forward slowly to get closer
                self.movement.forward(0.05, 1)
                time.sleep(0.2)
            
            print(f"Failed to reach object in attempt {retry + 1}")
        
        print(f"Failed to reach object after {max_retries + 1} attempts with adjustments")
        return False
    
    def _lift_object(self) -> bool:
        """Lift object until distance sensor shows object is lifted"""
        print("Starting lift operation...")
        
        for iteration in range(Config.MAX_LIFT_ATTEMPTS):
            lift_motor_up(0.1, 1)
            
            # Check distance sensor - when object is lifted, distance increases
            distance_values = get_distance_values()
            left_distance = distance_values[0]
            
            print(f"Lift attempt {iteration + 1}: Distance = {left_distance} cm")
            
            # Object is lifted when distance >= 8cm
            if left_distance >= 8:
                print(f"Object lifted successfully (distance: {left_distance} cm)")
                self.movement.stop()
                return True
            
            # Check weight as safety limit
            weight = read_weights()
            total_weight = sum(weight)
            
            if total_weight >= Config.MAX_WEIGHT_THRESHOLD:
                print(f"Weight limit exceeded: {total_weight}")
                self.attempt_place()
                return False
        
        print(f"Lift failed after {Config.MAX_LIFT_ATTEMPTS} attempts")
        self.movement.stop()
        return False
    
    def _return_to_path(self):
        """Return to path after pickup/place operation"""
        print("Returning to path")
        self.movement.backward(0.5, 1)
        self.movement.turn_right(2.18, 1)  # ~180 degrees