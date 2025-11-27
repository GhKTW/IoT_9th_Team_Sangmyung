"""
Test script for debugging turn_right motor function
"""
import time
from sensors import *
from models import RobotState
from movement import MovementController

def test_turn_right():
    """Test turn_right function with various parameters"""
    
    print("=== Turn Right Test ===")
    
    # Initialize
    robot_state = RobotState()
    movement = MovementController(robot_state)
    
    try:
        # Test 1: Basic turn right with current speed
        print("\n[Test 1] Turn right with default speed (0.6 * 0.7 = 0.42)")
        print("Calling turn_right(0.4, 1)...")
        movement.turn_right(0.4, 1)
        print("Done. Did it turn?")
        time.sleep(2)
        
        # Test 2: Turn right with full speed
        print("\n[Test 2] Turn right with full speed (1.0)")
        print("Calling turn_right(1.0, 1.0)...")
        movement.turn_right(1.0, 1.0)
        print("Done. Did it turn?")
        time.sleep(2)
        
        # Test 3: Turn right without auto-stop (continuous)
        print("\n[Test 3] Turn right continuous (no duration)")
        print("Calling turn_right(speed=1.0)...")
        movement.turn_right(speed=1.0)
        print("Turning for 2 seconds...")
        time.sleep(2)
        print("Stopping...")
        movement.stop()
        time.sleep(2)
        
        # Test 4: Manual motor control
        print("\n[Test 4] Manual motor control")
        print("Calling leftMotorForward(1.0) + rightMotorBackward(1.0)...")
        leftMotorForward(1.0)
        rightMotorBackward(1.0)
        print("Motors running for 2 seconds...")
        time.sleep(2)
        print("Stopping...")
        stop_all()
        time.sleep(2)
        
        # Test 5: Compare with turn_left
        print("\n[Test 5] Turn left for comparison")
        print("Calling turn_left(1.0, 1.0)...")
        movement.turn_left(1.0, 1.0)
        print("Done. Did it turn?")
        time.sleep(2)
        
        # Test 6: Test forward (sanity check)
        print("\n[Test 6] Forward for comparison")
        print("Calling forward(1.0, 1.0)...")
        movement.forward(1.0, 1.0)
        print("Done. Did it move forward?")
        time.sleep(2)
        
        print("\n=== All tests completed ===")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        print("Stopping all motors...")
        movement.stop()
        print("Test finished")

if __name__ == "__main__":
    # Initialize hardware
    print("Initializing hardware...")
    init_spi()
    
    print("\nStarting turn right test in 3 seconds...")
    print("Press Ctrl+C to stop at any time")
    time.sleep(3)
    
    test_turn_right()