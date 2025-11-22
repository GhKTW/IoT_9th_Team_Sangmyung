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




# ====================================================
# =====================이동 관련 START======================
# ====================================================
# 이동 관련 전역변수
DEFAULT_SPEED = 0.6
_current_speed = DEFAULT_SPEED   # 기본 PWM 값 (0.0 ~ 1.0)


# 기본 속도 설정 (PWM 값)
def set_speed(value: float):
    global _current_speed
    _current_speed = max(0.0, min(1.0, value))

def get_speed() -> float:
    return _current_speed

#멈춤 
def stop():
    stop_all()
#브레이크 
def brake():
    brake_all()

#전진
def move_forward(duration: float | None = None, speed: float | None = None):
    if speed is None:
        speed = _current_speed
    leftMotorForward(speed)
    rightMotorForward(speed)
    if duration is not None:
        time.sleep(duration)
        stop()
#후진
def move_backward(duration: float | None = None, speed: float | None = None):
    if speed is None:
        speed = _current_speed
    leftMotorBackward(speed)
    rightMotorBackward(speed)
    if duration is not None:
        time.sleep(duration)
        stop()
#좌회전
def turn_left(duration: float | None = None, speed: float | None = None):
    if speed is None:
        speed = _current_speed * 0.7  # 회전은 약간 느리게
    leftMotorBackward(speed)
    rightMotorForward(speed)
    if duration is not None:
        time.sleep(duration)
        stop()
#우회전
def turn_right(duration: float | None = None, speed: float | None = None):
    if speed is None:
        speed = _current_speed * 0.7
    leftMotorForward(speed)
    rightMotorBackward(speed)
    if duration is not None:
        time.sleep(duration)
        stop()

# ====================================================
# =====================이동 관련 END======================
# ====================================================


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

# =========================================================
# =====================타겟 트래킹 관련 START======================
# =========================================================

FRAME_WIDTH_DEFAULT = 320 #가로가 320px /정중앙 x 좌표 160px
DEAD_ZONE = 20   # 중앙 ±20px

#객체추적 모드 ON/OFF 상태 전역변수
_tracking_enabled = True

#객체 추적 모드 켜기/ 이후 track_step()동작
def enable_tracking():
    global _tracking_enabled
    _tracking_enabled = True

#객체 추적 모드 끄기/라인트레이서이동중 끌 수 있게
def disable_tracking():
    global _tracking_enabled
    _tracking_enabled = False
    stop()

#카메라에서 얻은 객체 중심 x좌표를 오프셋으로 움직이는 함수
def track_step(x_center: int | None,
               frame_width: int = FRAME_WIDTH_DEFAULT):
    if not _tracking_enabled:
        return

    if x_center is None:
        # 객체 못 봤으면 그냥 멈춰 있는 쪽이 안전
        stop()
        return

    center_x = frame_width // 2
    error = x_center - center_x   # 음수: 왼쪽 / 양수: 오른쪽

    # 객체 추적 모드일 때는 기본 속도 0.5 /movement.py의 _current_speed = 0.5로 세팅
    # 현재는 값을 바꿔서 조절해야함
    set_speed(0.5)

    if abs(error) <= DEAD_ZONE:
        # 거의 가운데 → 직진
        move_forward()
    elif error < 0:
        # 목표가 왼쪽에 있음 → 왼쪽으로 회전
        turn_left()
    else:
        # 목표가 오른쪽 → 오른쪽 회전
        turn_right()

# =========================================================
# =====================타겟 트래킹 관련 END======================
# =========================================================





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
