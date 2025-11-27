"""
Automatic light control based on ambient light sensor
"""
import time
import threading

from sensors import get_light_value, lightOn, lightOff
from models import RobotState


class LightController:
    """Handles automatic light control based on ambient light"""
    
    def __init__(self, robot_state: RobotState, threshold: int = 10, check_interval: float = 0.5):
        """
        Initialize light controller
        
        Args:
            robot_state: Global robot state
            threshold: Light value threshold (light turns on when value <= threshold)
            check_interval: Time between sensor checks in seconds
        """
        self.robot_state = robot_state
        self.threshold = threshold
        self.check_interval = check_interval
        self.light_is_on = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start the light monitoring thread"""
        self.monitor_thread = threading.Thread(
            target=self._monitor_light_loop,
            daemon=True
        )
        self.monitor_thread.start()
        print(f"Light monitoring started (threshold: {self.threshold})")
    
    def _monitor_light_loop(self):
        """Main monitoring loop (runs in thread)"""
        while not self.robot_state.exit_flag:
            try:
                light_value = get_light_value()
                
                # Turn light on when dark
                if light_value <= self.threshold and not self.light_is_on:
                    lightOn()
                    self.light_is_on = True
                    print(f"Light turned ON (ambient light: {light_value})")
                
                # Turn light off when bright
                elif light_value > self.threshold and self.light_is_on:
                    lightOff()
                    self.light_is_on = False
                    print(f"Light turned OFF (ambient light: {light_value})")
                
            except Exception as e:
                print(f"Light monitoring error: {e}")
            
            time.sleep(self.check_interval)
    
    def stop(self):
        """Stop monitoring and turn off light"""
        if self.light_is_on:
            lightOff()
            self.light_is_on = False
            print("Light turned OFF (monitoring stopped)")