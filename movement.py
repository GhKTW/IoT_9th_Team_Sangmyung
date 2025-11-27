"""
Movement control for the robot
"""
import time
from typing import Optional

from sensors import *
from config import Config
from models import RobotState


class MovementController:
    """Controls robot movement"""
    
    def __init__(self, robot_state: RobotState):
        self.robot_state = robot_state
    
    def set_speed(self, value: float):
        """Set movement speed (0.0 to 1.0)"""
        self.robot_state.current_speed = max(0.0, min(1.0, value))
    
    @staticmethod
    def stop():
        """Stop all motors"""
        stop_all()
    
    @staticmethod
    def brake():
        """Apply brake"""
        brake_all()
    
    def forward(self, duration: Optional[float] = None, speed: Optional[float] = None):
        """Move forward"""
        speed = speed or self.robot_state.current_speed
        leftMotorForward(speed)
        rightMotorForward(speed)
        if duration:
            time.sleep(duration)
            stop_all()
    
    def backward(self, duration: Optional[float] = None, speed: Optional[float] = None):
        """Move backward"""
        speed = speed or self.robot_state.current_speed
        leftMotorBackward(speed)
        rightMotorBackward(speed)
        if duration:
            time.sleep(duration)
            stop_all()
    
    def turn_left(self, duration: Optional[float] = None, speed: Optional[float] = None):
        """Turn left"""
        speed = speed or (self.robot_state.current_speed * Config.TURN_SPEED_RATIO)
        leftMotorBackward(speed)
        rightMotorForward(speed)
        if duration:
            time.sleep(duration)
            stop_all()
    
    def turn_right(self, duration: Optional[float] = None, speed: Optional[float] = None):
        """Turn right"""
        speed = speed or (self.robot_state.current_speed * Config.TURN_SPEED_RATIO)
        leftMotorForward(speed)
        rightMotorBackward(speed)
        if duration:
            time.sleep(duration)
            stop_all()


class LineFollower:
    """Handles line following behavior"""
    
    @staticmethod
    def follow_to_target(movement: MovementController, timeout: float = 30.0) -> bool:
        """
        Follow line until reaching target (all sensors detect line)
        
        Args:
            movement: Movement controller
            timeout: Maximum time to wait for line in seconds
        
        Returns:
            True if line detected, False if timeout
        """
        start_time = time.time()
        
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                print(f"Line following timeout after {timeout}s")
                movement.stop()
                return False
            
            line_values = get_line_values()
            left, center, right = line_values[0], line_values[1], line_values[2]

            if (left == 1 or center == 1 or right == 1):
                movement.stop()
                return True
            
            time.sleep(0.01)  # Small delay to prevent busy waiting