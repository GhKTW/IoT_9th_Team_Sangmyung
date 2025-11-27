"""
Line tracer monitoring with dedicated thread
Optimized for maximum detection accuracy
"""
import time
import threading
from typing import List

from sensors import get_line_values
from models import RobotState


class LineMonitor:
    """Monitors line tracer sensors with high accuracy"""
    
    def __init__(self, robot_state: RobotState, check_interval: float = 0.02):
        """
        Initialize line monitor
        
        Args:
            robot_state: Global robot state
            check_interval: Time between sensor checks in seconds (default: 20ms for fast response)
        """
        self.robot_state = robot_state
        self.check_interval = check_interval
        self.monitor_thread = None
        
        # Current line sensor values (global access)
        self.line_values = [0, 0, 0]
        
        # Detection state tracking for accuracy
        self.last_detected_state = False
        self.detection_count = 0
    
    def start_monitoring(self):
        """Start the line monitoring thread"""
        self.monitor_thread = threading.Thread(
            target=self._monitor_line_loop,
            daemon=True
        )
        self.monitor_thread.start()
        print(f"Line monitoring started (check interval: {self.check_interval}s, optimized for accuracy)")
    
    def _monitor_line_loop(self):
        """Main monitoring loop (runs in thread) - optimized for detection accuracy"""
        while not self.robot_state.exit_flag:
            try:
                # Read and update line sensor values
                self.line_values = get_line_values()
                
                # Track detection state changes for logging
                current_detected = any(v == 1 for v in self.line_values)
                
                if current_detected != self.last_detected_state:
                    if current_detected:
                        self.detection_count += 1
                        print(f"🟢 LINE DETECTED #{self.detection_count}: {self.line_values}")
                    else:
                        print(f"⚪ Line lost: {self.line_values}")
                    self.last_detected_state = current_detected
                
            except Exception as e:
                print(f"Line monitoring error: {e}")
            
            time.sleep(self.check_interval)
    
    def get_line_values(self) -> List[int]:
        """Get current line sensor values"""
        return self.line_values
    
    def is_line_detected(self) -> bool:
        """
        Check if any sensor detects line
        Optimized for accuracy - checks any sensor detecting black
        """
        return any(v == 1 for v in self.line_values)
    
    def get_detection_details(self) -> dict:
        """
        Get detailed detection information for debugging
        
        Returns:
            Dictionary with sensor states and detection status
        """
        return {
            'left': self.line_values[0],
            'center': self.line_values[1],
            'right': self.line_values[2],
            'detected': self.is_line_detected(),
            'count': self.detection_count
        }