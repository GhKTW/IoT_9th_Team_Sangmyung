import cv2
import subprocess
import shlex
import numpy as np
import threading
import socket
import time
from ultralytics import YOLO

from sensors import *

# -------------------------------
# Initialize SPI for sensors
# -------------------------------
init_spi()

# -------------------------------
# YOLOv8n Model
# -------------------------------
model = YOLO('yolov8n.pt')  # Load pretrained YOLOv8n model
model.conf = 0.4
model.overrides['imgsz'] = 640

# -------------------------------
# Target classes
# -------------------------------
TARGET_CLASSES = {47: "apple", 46: "banana", 49: "orange", 7: "truck"}

# -------------------------------
# Global variables
# -------------------------------
buffer = bytearray()
camera_lock = threading.Lock()
buffer_lock = threading.Lock()

frame_buffer = []
buffer_ready = threading.Event()

process = None
frame_idx = 0
process_every_n_frames = 15

UDP_IP = "192.168.0.10"
UDP_PORT = 5005
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

MAX_BUFFER_SIZE = 500_000
is_buffering = False
exit_flag = False

# -------------------------------
# Latest centers (thread-safe)
# -------------------------------
latest_centers = []  # [(name, x_center, y_center), ...]
latest_centers_lock = threading.Lock()

latest_detection_id = 0
latest_detection_id_lock = threading.Lock()


# -------------------------------
# Start camera process
# -------------------------------
def start_camera_process(camera_index):
    global process
    cmd = f'libcamera-vid --inline --vflip --hflip --nopreview -t 0 --codec mjpeg ' \
          f'--width 640 --height 640 --framerate 30 -o - --camera {camera_index}'
    process = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )


# -------------------------------
# Detect objects using YOLOv8
# -------------------------------
def detect_object(image):
    global latest_detection_id

    results = model(image, classes=list(TARGET_CLASSES.keys()))
    boxes = results[0].boxes

    fruits = []
    for box in boxes:
        cls_id = int(box.cls[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        fruits.append((cls_id, x1, y1, x2, y2))

        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(image, TARGET_CLASSES[cls_id], (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    # -------------------------------
    # UPDATE latest_centers
    # -------------------------------
    centers = []
    for cls_id, x1, y1, x2, y2 in fruits:
        x_center = int((x1 + x2) / 2)
        y_center = int((y1 + y2) / 2)
        centers.append((TARGET_CLASSES[cls_id], x_center, y_center))

    with latest_centers_lock:
        latest_centers[:] = centers

    # -------------------------------
    # UPDATE detection id
    # -------------------------------
    with latest_detection_id_lock:
        latest_detection_id += 1

    return image, fruits



# -------------------------------
# Read frames from camera
# -------------------------------
def read_frames():
    global buffer, frame_idx, exit_flag

    while not exit_flag:
        with camera_lock:
            if process is None:
                continue

            try:
                chunk = process.stdout.read(4096)
            except Exception:
                continue

            if not chunk:
                continue

            buffer.extend(chunk)
            if len(buffer) > MAX_BUFFER_SIZE:
                buffer = buffer[-MAX_BUFFER_SIZE:]

        a = buffer.find(b'\xff\xd8')
        b = buffer.find(b'\xff\xd9')

        if a != -1 and b != -1 and b > a:
            jpg = buffer[a:b+2]
            del buffer[:b+2]

            image = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                continue

            frame_idx += 1

            if frame_idx % process_every_n_frames == 0:
                processed_image, fruits = detect_object(image)

                # send UDP
                for cls_id, x1, y1, x2, y2 in fruits:
                    x_center = int((x1 + x2) / 2)
                    y_center = int((y1 + y2) / 2)
                    msg = f"{TARGET_CLASSES[cls_id]}:{x_center},{y_center}"
                    udp_socket.sendto(msg.encode(), (UDP_IP, UDP_PORT))

                cv2.imshow("YOLOv8 Detection", processed_image)
                if cv2.waitKey(1) & 0xFF == 27:
                    exit_flag = True
                    break

            if is_buffering:
                with buffer_lock:
                    frame_buffer.append(image)
                    buffer_ready.set()


# -------------------------------
# Main execution
# -------------------------------
if __name__ == "__main__":
    start_camera_process(0)
    frame_reader_thread = threading.Thread(target=read_frames, daemon=True)
    frame_reader_thread.start()

    while not exit_flag:
        # You can read latest center coordinates anywhere:
        with latest_centers_lock:
            if latest_centers:
                print("Latest detection:", latest_centers)

        time.sleep(0.1)

    cv2.destroyAllWindows()
    if process:
        process.terminate()
