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
setup_loadcell()


# -------------------------------
# YOLOv8n Model
# -------------------------------
model = YOLO('yolov8n.pt')
model.conf = 0.4
model.overrides['imgsz'] = 320      # 화면 크기 320
model.overrides['verbose'] = False  # 디버그 출력 해제
# -------------------------------
# Target classes
# -------------------------------
TARGET_CLASSES = {47: "apple", 46: "banana", 49: "orange"}
TRUCK_CLASS = {7: "truck"}
# -------------------------------
# Global State
# -------------------------------
exit_flag = False
latest_centers = []
latest_centers_lock = threading.Lock()
process_every_n_frames = 15
frame_idx = 0

process = None

line_values = []


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
        print(latest_centers)
    return centers


# -------------------------------
# 프레임 읽기 쓰레드
# -------------------------------
def read_frames():
    global frame_idx, exit_flag
    
    buffer = b''  # 버퍼 추가
    
    while not exit_flag:
        if process is None:
            continue

        chunk = process.stdout.read(4096)

        if not chunk:
            continue

        buffer += chunk  # 버퍼에 누적
        
        # JPEG 시작과 끝 마커 찾기
        while True:
            start = buffer.find(b'\xff\xd8')
            end = buffer.find(b'\xff\xd9')

            if start != -1 and end != -1 and end > start:
                jpg = buffer[start:end + 2]
                buffer = buffer[end + 2:]  # 처리된 부분 제거
                
                image = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)

                if image is not None:
                    frame_idx += 1

                    if frame_idx % process_every_n_frames == 0:
                        detect_object(image)
            else:
                # 완전한 프레임이 없으면 더 읽기
                break
        
        # 버퍼가 너무 커지는 것 방지 (10MB 이상이면 초기화)
        if len(buffer) > 10 * 1024 * 1024:
            buffer = b''
            
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
def track_step(target_class: str, is_going_to_lift: bool):
    print("물건 가지러 / 놓으러 가기 시작")
    while True:
        line_values = get_line_values()

        # --- 트럭과 target_object를 찾기 ---
        target_object = next((obj for obj in latest_centers if obj[0] == target_class), None)
        truck_object  = next((obj for obj in latest_centers if obj[0] == TRUCK_CLASS), None)

        # ----------------------- CASE 1 : PICK MODE -----------------------
        if is_going_to_lift:
            if target_object is None:
                turn_left(0.2, 0.5)
                time.sleep(0.2)
                print("들기 모드, 객체 탐지 실패")
                continue
            
            # 물체 찾았으면 그 객체의 중심을 기반으로 정렬
            target_x = target_object[1]

        # ----------------------- CASE 2 : PLACE MODE -----------------------
        else:
            # 목적지 조건: target_class + truck_class 모두 존재해야 함
            if target_object is None or truck_object is None:
                turn_left(0.2, 0.5)
                time.sleep(0.2)
                print("놓기 모드, 객체 탐지 실패1")
                continue
            
            # 두 객체의 x좌표가 충분히 가까워야 목적지로 인정
            if abs(target_object[1] - truck_object[1]) > 50:
                # 정렬 기준은 트럭 (목표는 트럭에 물체 놓기)
                turn_left(0.2, 0.5)
                time.sleep(0.2)
                print("놓기 모드, 객체 탐지 실패2")
                continue
            else:
                target_x = truck_object[1]
                print("객체 탐지 성공: " + target_x)

        # ----------------------- MOVEMENT CONTROL -----------------------

        center_x = FRAME_WIDTH_DEFAULT // 2
        error = target_x - center_x

        set_speed(0.5)

        # 얼추 중앙, 직진
        if abs(error) <= DEAD_ZONE:
            print("찾아가는중... 전진")
            move_forward(0.5, 0.5)
        # 물체가 더 왼쪽에 있음, 좌회전
        elif error < 0:
            print("찾아가는중... 우회전")
            turn_right(0.2, 0.5)
        # 물체가 더 오른쪽에 있음, 우회전
        else:
            turn_left(0.2, 0.5)

        # --------- EXIT CONDITION: line detected ---------
        if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
            print("라인 검출, 목적지 도착")
            break


    # ----------------------- FINAL ACTION -----------------------
    stop()

    if is_going_to_lift:
        print("물건 들기 시도")
        success_lifting = attempt_lift()
        return success_lifting
        
    else:
        print("물건 놓기 시도")
        success_placing = attempt_place()
        return success_placing

    

# =========================================================
# =====================타겟 트래킹 관련 END======================
# =========================================================

# =========================================================
# =====================물체 들어올리기 관련 START======================
# =========================================================

def attempt_lift():
    print("물건 들기 시도 시작")
    line_values = get_line_values()
    # 물체의 바로 앞에 있는 가로 선을 인식할 때 까지 전진
    while (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 1):
        print("목적지로 이동")
        # 0 0 0: 지금 안보이니까 전진
        if (line_values[0] == 0 and line_values[1] == 0 and line_values[2] == 0):
            move_forward(0.1)
            continue

        # 1 0 0, 1 1 0: 왼쪽에 선이 있으니까 왼쪽으로 약간 회전
        elif (line_values[0] == 1 and line_values[1] == 0 and line_values[2] == 0) or (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 0):
            turn_left(0.1)
            continue

        # 0 0 1, 0 1 1: 오른쪽에 선이 있으니까 오른쪽으로 약간 회전
        elif (line_values[0] == 0 and line_values[1] == 0 and line_values[2] == 1) or (line_values[0] == 0 and line_values[1] == 1 and line_values[2] == 1):
            turn_right(0.1)
            continue

        # 0 1 0: 가운데 선이 있으니까 직진
        elif (line_values[0] == 0 and line_values[1] == 1 and line_values[2] == 0):
            move_forward(0.1)
            continue

        # 1 1 1: 선을 완전히 인식했으면 멈춤
        elif (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 1):
            # 이 시점에서는 아마 물체 바로 앞에 도달했을 것
            print("물건 앞 도착")
            stop()
            break
            
    # 가운데 거리센서 값 읽어서 물체가 있는지 확인
    center_distance = get_distance_values()[1]  # 가운데 센서

    # 물건이 바로 앞에 없는 경우 추가
    ready_to_lift = False
    if center_distance > 10:  # 10cm 이내에 물체가 없으면
        for i in range(10):
            center_distance = get_distance_values()[1]
            if (center_distance <= 10):
                print("물건 들기 준비 완료")
                ready_to_lift = True
                break
            else:
                ready_to_lift = False
                move_forward(0.2, 0.5)

    lifted_successful = False
    if ready_to_lift:
    # 특정 높이만큼 들기
        idx = 0
        for idx in range(15): # 최대 10번 반복 들기 시도(10번 시도하면 다 들었다고 가정)
            lift_motor_up(0.1, 0.5)  # 속도 0.5로 들기
            # 조금 들고 로드셀 값 읽기(한계 무게 초과인지를 계속 확인)
            weight = read_weights()
            total_weight = weight[0] + weight[1]
            if total_weight >= 55000:  # 총 무게가 기준치 이하면 계속 들기
                print("물건이 너무 무거움, 포기")
                break
        else:
            print("물건 들기 성공")
            lifted_successful = True

        if (not lifted_successful):
            # 한계 무게가 초과되었다면 다시 내리기
            lift_motor_down(idx, 0.5)  # 속도 0.5로 내리기
        # 들었건 말건 여기서 할 일은 끝남

    # 일단 후진해서 180도 돌고, lift_successful 플래그에 따라 다음 동작 실행
    print("들기 시도 종료, 뒤로 가서 180도 회전")
    move_backward(1.0)  # 1초 후진
    turn_right(2.18)    # 2.18초 우회전 (대략 180도)

    if (lifted_successful):
        # 들기에 성공했으면 내려놓기 함수 호출
        print("물건 들기 성공, 들기 함수 종료")
        return True
    elif(not lifted_successful):
        # 들기에 실패했다면, 다음 함수를 실행하지 않고 종료. 다음 타겟 탐색으로 넘어감
        print("물건 들기 실패, 들기 함수 종료")
        return False


def attempt_place():
    line_values = get_line_values()
    # 물체의 바로 앞에 있는 가로 선을 인식할 때 까지 전진
    while (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 1):
        # 0 0 0: 지금 안보이니까 전진
        if (line_values[0] == 0 and line_values[1] == 0 and line_values[2] == 0):
            move_forward(0.1)
            continue

        # 1 0 0, 1 1 0: 왼쪽에 선이 있으니까 왼쪽으로 약간 회전
        elif (line_values[0] == 1 and line_values[1] == 0 and line_values[2] == 0) or (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 0):
            turn_left(0.1, 0.5)
            continue

        # 0 0 1, 0 1 1: 오른쪽에 선이 있으니까 오른쪽으로 약간 회전
        elif (line_values[0] == 0 and line_values[1] == 0 and line_values[2] == 1) or (line_values[0] == 0 and line_values[1] == 1 and line_values[2] == 1):
            turn_right(0.1, 0.5)
            continue

        # 0 1 0: 가운데 선이 있으니까 직진
        elif (line_values[0] == 0 and line_values[1] == 1 and line_values[2] == 0):
            move_forward(0.1, 0.5)
            continue

        # 1 1 1: 선을 완전히 인식했으면 멈춤
        elif (line_values[0] == 1 and line_values[1] == 1 and line_values[2] == 1):
            # 이 시점에서는 아마 물체 바로 앞에 도달했을 것
            stop()
            break
    
    # 물체 놓을 곳 바로 앞에 왔으니까, 내려놓기
    lift_motor_down(10, 0.5)

    move_backward(1.0)  # 1초 후진
    turn_right(2.18)    # 2.18초 우회전 (대략 180도)
    return True



# =========================================================
# =====================물체 들어올리기 관련 END======================
# =========================================================


# -------------------------------
# Main Loop
# -------------------------------
if __name__ == "__main__":
    # 카메라 인식 쓰레드 시작
    start_camera_process(0)
    t = threading.Thread(target=read_frames, daemon=True)
    t.start()

    # 여기서부터 모든 로직 구현을 하자!
    # 시작: 목표 설정부터(사과 -> 바나나 -> 오렌지) 순으로 처리할거임
    target_order = [47, 46, 49]  # apple, banana, orange
    current_target_idx = 0

    # 객체 찾기
    # TODO: 객체 찾는 함수 구현, 사과와 차 모양이 동시에 있으면 그 곳이 시작점

    # 탐지 후 프레임 내에 찾는게 없으면 왼쪽으로 회전
    try:
        while not exit_flag:  # 무한 반복
            target_id = target_order[current_target_idx]
            main_target = TARGET_CLASSES[target_id]
            print(f"Current target: {main_target}")
            
            # PICK (들기)
            is_going_to_lift = True
            lifting_state = track_step(main_target, is_going_to_lift)
            
            print(f"놓기 여부 {lifting_state}")
            # PLACE (놓기) - 들기 성공했을 때만
            if lifting_state == 1:
                is_going_to_lift = False
                track_step(main_target, is_going_to_lift)
            
            # 다음 타겟으로 이동
            current_target_idx = (current_target_idx + 1) % len(target_order)
            
    except KeyboardInterrupt:
        print("프로그램 종료")
        exit_flag = True
    finally:
        stop()
        if process:
            process.terminate()