import cv2
import subprocess
import shlex
import numpy as np
import threading
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
model = YOLO('yolov8n.pt')
model.conf = 0.4
model.overrides['imgsz'] = 320

# -------------------------------
# Target classes
# -------------------------------
TARGET_CLASSES = {47: "apple", 46: "banana", 49: "orange"}

# -------------------------------
# Global State
# -------------------------------
exit_flag = False
latest_centers = []
latest_centers_lock = threading.Lock()
process_every_n_frames = 15
frame_idx = 0

process = None


# -------------------------------
# Start camera
# -------------------------------
def start_camera_process(camera_index):
    global process
    cmd = f'libcamera-vid --inline --vflip --nopreview -t 0 --codec mjpeg ' \
          f'--width 320 --height 320 --framerate 30 -o - --camera {camera_index}'
    process = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )


# -------------------------------
# YOLO 객체 검출 함수
# -------------------------------
def detect_object(image):
    results = model(image, classes=list(TARGET_CLASSES.keys()))
    boxes = results[0].boxes

    centers = []

    for box in boxes:
        cls_id = int(box.cls[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        x_center = int((x1 + x2) / 2)
        y_center = int((y1 + y2) / 2)

        centers.append((TARGET_CLASSES[cls_id], x_center, y_center))

    # 최신값 갱신
    with latest_centers_lock:
        global latest_centers
        latest_centers = centers[:]

    return centers


# -------------------------------
# 프레임 읽기 쓰레드
# -------------------------------
def read_frames():
    global frame_idx, exit_flag

    while not exit_flag:
        if process is None:
            continue

        chunk = process.stdout.read(4096)

        if not chunk:
            continue

        # 단일 프레임 인식용 MJPEG 찾기
        start = chunk.find(b'\xff\xd8')
        end   = chunk.find(b'\xff\xd9')

        if start != -1 and end != -1 and end > start:
            jpg = chunk[start:end + 2]
            image = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)

            if image is None:
                continue

            frame_idx += 1

            if frame_idx % process_every_n_frames == 0:
                detect_object(image)


# -------------------------------
# Main Loop
# -------------------------------
if __name__ == "__main__":
    start_camera_process(0)

    t = threading.Thread(target=read_frames, daemon=True)
    t.start()

    while not exit_flag:
        with latest_centers_lock:
            if latest_centers:
                print("Latest detection:", latest_centers)

        time.sleep(0.1)

    if process:
        process.terminate()
