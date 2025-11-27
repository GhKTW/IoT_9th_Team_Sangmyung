"""
Camera management and frame processing
"""
import cv2
import subprocess
import shlex
import numpy as np

from config import Config
from detection import ObjectDetector
from models import RobotState


class CameraManager:
    """Manages camera capture and processing"""
    
    def __init__(self, detector: ObjectDetector, robot_state: RobotState):
        self.detector = detector
        self.robot_state = robot_state
    
    def start_capture(self):
        """Start camera capture process"""
        cmd = (
            f'libcamera-vid --inline --vflip --nopreview -t 0 --codec mjpeg '
            f'--width {Config.FRAME_WIDTH} --height {Config.FRAME_HEIGHT} '
            f'--framerate {Config.FRAME_RATE} -o - --camera {Config.CAMERA_INDEX}'
        )
        self.robot_state.camera_process = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
    
    def read_frames_loop(self):
        """Main frame reading loop (runs in thread)"""
        buffer = b''
        
        while not self.robot_state.exit_flag:
            if self.robot_state.camera_process is None:
                continue
            
            chunk = self.robot_state.camera_process.stdout.read(4096)
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
        self.robot_state.frame_idx += 1
        
        if self.robot_state.frame_idx % Config.PROCESS_EVERY_N_FRAMES == 0:
            objects = self.detector.detect(image)
            self.robot_state.update_detection(objects)
            print(f"Detection #{self.robot_state.detection_sequence}: "
                  f"{[(obj.class_name, obj.x_center) for obj in objects]}")