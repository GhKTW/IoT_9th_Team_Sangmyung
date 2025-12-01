import cv2
import subprocess
import shlex
import numpy as np
import threading
import time
import requests
from ultralytics import YOLO
from sensors import *

# ==========================================
# 서버 통신 설정
# ==========================================
SERVER_URL = "http://192.168.137.3:8080/api/sensor/data"

MAX_LIFT_STOP_RAW_VALUE = 55000 # 들기 동작을 멈추는 최대 한계값 (프론트엔드 게이지 100% 기준)
OVERLOAD_WARNING_THRESHOLD = MAX_LIFT_STOP_RAW_VALUE * 0.8 # 프론트엔드에서 붉은색 경고를 표시하는 기준 (80% / 44000)

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
model.overrides['imgsz'] = 640      # 화면 크기 640
model.overrides['verbose'] = False  # 디버그 출력 해제

# -------------------------------
# Target classes
# -------------------------------
TARGET_CLASSES = {47: "apple", 46: "banana", 50: "broccoli", 7: "truck"}  # truck 추가
TRUCK_CLASS_NAME = "truck"  # 문자열로 비교할 이름

# -------------------------------
# Global State
# -------------------------------
exit_flag = False
latest_centers = []
latest_centers_lock = threading.Lock()
process_every_n_frames = 15
frame_idx = 0
_is_light_on_status = False

# MOVING
FORWARD     = [1, 0, 1, 0]
BACKWARD    = [0, 1, 0, 1]
LEFT        = [1 ,0, 0, 1]
RIGHT       = [0, 1, 1, 0]

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
def move_forward(duration: float | None = None):
    set_motor(FORWARD)
    time.sleep(duration)
    stop()
#후진
def move_backward(duration: float | None = None):
    set_motor(BACKWARD)
    time.sleep(duration)
    stop()
#좌회전
def turn_left(duration: float | None = None):
    set_motor(LEFT)
    time.sleep(duration)
    stop()
#우회전
def turn_right(duration: float | None = None):
    set_motor(RIGHT)
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
          f'--width 640 --height 640 --framerate 30 -o - --camera {camera_index}'
    process = subprocess.Popen(
        shlex.split(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL
    )


# -------------------------------
# YOLO 객체 검출 함수
# -------------------------------
def detect_object(image):
    # truck 포함하여 검출
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
        print(f"Detected: {latest_centers}")  # 디버깅용
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

FRAME_WIDTH_DEFAULT = 640 #가로가 320px /정중앙 x 좌표 160px
DEAD_ZONE = 20   # 중앙 ±20px

#객체추적 모드 ON/OFF 상태 전역변수
# _tracking_enabled = True

# #객체 추적 모드 켜기/ 이후 track_step()동작
# def enable_tracking():
#     global _tracking_enabled
#     _tracking_enabled = True

# #객체 추적 모드 끄기/라인트레이서이동중 끌 수 있게
# def disable_tracking():
#     global _tracking_enabled
#     _tracking_enabled = False
#     stop()

#카메라에서 얻은 객체 중심 x좌표를 오프셋으로 움직이는 함수
def track_step(target_class: str, is_going_to_lift: bool):
    print("물건 가지러 / 놓으러 가기 시작")
    search_count = 0
    max_search_attempts = 500000  # 최대 탐색 횟수

    while True:
        line_values = get_line_values()

        # latest_centers 복사본 사용 (thread-safe)
        with latest_centers_lock:
            current_centers = latest_centers[:]

        # --- 트럭과 target_object를 찾기 ---
        target_object = next((obj for obj in current_centers if obj[0] == target_class), None)
        truck_object  = next((obj for obj in current_centers if obj[0] == TRUCK_CLASS_NAME), None)

        print(f"Target: {target_object}, Truck: {truck_object}")  # 디버깅

        # ----------------------- CASE 1 : PICK MODE -----------------------
        if is_going_to_lift:
            if target_object is None:
                search_count += 1
                if search_count > max_search_attempts:
                    print("객체를 찾지 못함, 탐색 중단")
                    return False

                print(f"들기 모드, {target_class} 탐지 실패 - 좌회전 탐색")
                turn_left(0.4)
                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue

            if truck_object is not None:
                print(f"들기 모드, {target_class}과 트럭이 동시에 감지됨 - 회피 동작")
                turn_left(0.4)  # 예: 우회전으로 잠시 회피
                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue

            search_count = 0  # 객체 발견 시 카운트 리셋
            target_x = target_object[1]

        # ----------------------- CASE 2 : PLACE MODE -----------------------
        else:
            if target_object is None or truck_object is None:
                search_count += 1
                if search_count > max_search_attempts:
                    print("목적지를 찾지 못함, 탐색 중단")
                    return False

                print(f"놓기 모드, 객체 탐지 실패 (target:{target_object is not None}, truck:{truck_object is not None})")
                turn_left(0.4)
                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue

            # 두 객체의 x좌표 차이 확인
            x_diff = abs(target_object[1] - truck_object[1])
            print(f"X 좌표 차이: {x_diff}")

            if x_diff > 70:
                search_count += 1
                if search_count > max_search_attempts:
                    print("정렬 실패, 탐색 중단")
                    return False

                print(f"놓기 모드, 정렬 필요 (차이: {x_diff})")
                turn_left(0.2)
                time.sleep(0.2)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue
            else:
                search_count = 0
                target_x = truck_object[1]
                print(f"객체 정렬 완료: truck at {target_x}")

        # ----------------------- MOVEMENT CONTROL -----------------------
        center_x = FRAME_WIDTH_DEFAULT // 2
        error = target_x - center_x
        scale = abs(error) / 320.0 * 0.45 + 0.05

        if abs(error) <= DEAD_ZONE:
            print("찾아가는중... 전진")
            move_forward(0.3)
            time.sleep(0.4)
        elif error < 0:
            print("찾아가는중... 우회전")
            turn_right(scale)
            # turn_right(0.2)
            time.sleep(0.4)
        else:
            print("찾아가는중... 좌회전")
            turn_left(scale)
            # turn_left(0.2)
            time.sleep(0.4)

        time.sleep(0.05)  # 안정화 대기

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
    # 이미 들 물체 앞에 있을 거임

    # 가운데 거리센서 값 읽어서 물체가 있는지 확인
    center_distance = get_distance_values()[1]  # 가운데 센서

    # 물건이 바로 앞에 없는 경우 추가
    ready_to_lift = False
    print(f"현재 내 앞 거리: {center_distance}")
    if center_distance > 10:  # 10cm 이내에 물체가 없으면
        print("가운데 거리센서, 물체 있는지 확인중...")
        for i in range(20):
            center_distance = get_distance_values()[1]
            print(f"조금씩 전진 시도 #{i}, 거리: {center_distance}")
            if (center_distance <= 10):
                print("물건 들기 준비 완료")
                ready_to_lift = True
                break
            else:
                move_forward(0.2)
                time.sleep(0.3)
        else:
            print("앞에 물체 없음, 들기 실패")
            ready_to_lift = False
    else:
        print("물체가 가까이 있음. 들기 준비 완료")
        ready_to_lift = True

    lifted_successful = False
    if ready_to_lift:
        # 특정 높이만큼 들기
        idx = 0
        for idx in range(40): # 최대 20번 반복 들기 시도
            print(f"lift_up #{idx}")
            lift_height = get_distance_values()[0]
            weight = read_weights()
            total_weight = weight[0] + weight[1]

            lift_motor_up(0.1, 0.5)  # 속도 0.5로 들기


            if lift_height >= 7:
                print("물건 끝까지 들기 완료")
                lifted_successful = True
                stop()
                break
            elif total_weight >= 55000:
                print("하중 제한 초과, 들기 실패")
                lifted_successful = False
                stop()
                break
            else:
                print("들기 종료 조건 미충족, 계속 시도")
                continue

        if (not lifted_successful):
            # 한계 무게가 초과되었다면 다시 내리기
            lift_down_weight()

    # 일단 후진해서 180도 돌고, lift_successful 플래그에 따라 다음 동작 실행
    print("들기 시도 종료, 뒤로 가서 180도 회전")
    move_backward(0.6)  # 1초 후진
    turn_left(4)    # 2.18초 우회전 (대략 180도)
    stop()


    if (lifted_successful):
        # 들기에 성공했으면 내려놓기 함수 호출
        print("물건 들기 성공, 들기 함수 종료")
        return True
    elif(not lifted_successful):
        # 들기에 실패했다면, 다음 함수를 실행하지 않고 종료. 다음 타겟 탐색으로 넘어감
        print("물건 들기 실패, 들기 함수 종료")
        return False


def attempt_place():
    # 물체 놓을 곳 바로 앞에 왔으니까, 내려놓기
    lift_down_weight()

    move_backward(0.7)  # 1초 후진
    turn_left(4)    # 2.18초 우회전 (대략 180도)
    stop()
    print("하차 끝")
    return True


def lift_down_weight():
    placed_successful = False
    # 최대 30번 반복 내리기 시도
    for i in range(30):
        lift_motor_down(0.1, 0.5)  # 속도 0.5로 내리기
        print("down...")
        # 조금 내리고 로드셀 값 읽기
        lift_height = get_distance_values()[0]
        weight = read_weights()
        total_weight = weight[0] + weight[1]
        print(total_weight)
        if total_weight <= 5000 or lift_height < 2.5:  # 총 무게가 기준치 이하면 내려놓기 완료
            print("내려놓기 끝")
            placed_successful = True
            break

    if placed_successful:
        print("내려놓기 성공")
    else:
        print("내려놓기 완료 (최대 시도 횟수 도달)")

# ----------------------------------------------------------------------------------
# [함수 사용 설명서]
#
# 1. 매개변수 설명
#   - detected_obj (str): 현재 감지했거나 들고 있는 물체 이름 (예: "apple", "banana", "none")
#   - status (str): 현재 지게차의 동작 상태 (예: "LIFTING", "SEARCHING", "ARRIVED", "OVERLOAD")
#   - total_weight_g (float, 옵션): (선택사항) 이미 읽어둔 로드셀 무게 값(g). 값을 넣으면 함수 안에서 센서를 다시 읽지 않음.
#   - is_overloaded (bool, 옵션): (선택사항) 과부하 여부(True/False)를 강제로 지정할 때 사용.
#
# 2. 사용 예시
#   CASE A: 이동/탐색 중 (무게 0, 센서 안 읽음)
#       -> payload = get_sensor_state("apple", "SEARCHING")
#       -> send_data(payload)
#
#   CASE B: 무게 측정 완료 후 (이미 읽은 무게 값을 재사용하여 전송)
#       -> payload = get_sensor_state("apple", "WEIGHING", total_weight_g=current_weight)
#       -> send_data(payload)
#
#   CASE C: 과부하 발생 시 (경고 상태 강제 전송)
#       -> payload = get_sensor_state("apple", "OVERLOAD", total_weight_g=current_weight, is_overloaded=True)
#       -> send_data(payload)
#   3. 상태-메시지 목록
#  'SEARCHING': return '🔍 물체 탐색 중';
#  'LIFTING': return '🏗️ 적재 중 (Lifting)';
#  'WEIGHING': return '⚖️ 무게 측정 중';
#  'TRANSPORTING': return '🚚 운송 중 (Moving)';
#  'UNLOADING': return '⬇️ 하역 중 (Dropping)';
#  'ARRIVED': return '🏁 작업 완료';
#  'OVERLOAD': return '⚠️ 과적 경고!';
# ----------------------------------------------------------------------------------


def get_sensor_state(detected_obj: str, status: str, total_weight_g: float | None = None, is_overloaded: bool | None = None) -> dict:

    global _is_light_on_status # 전역 상태 사용

    # --- 1. 무게 및 과부하 계산 (무게 관련 상태일 때만 센서 값 읽기) ---
    if status in ['LIFTING', 'WEIGHING', 'UNLOADING', 'OVERLOAD']:
        if total_weight_g is None:
            weight = read_weights()
            total_weight_g = weight[0] + weight[1]

        max_load = MAX_LIFT_STOP_RAW_VALUE
        weight_percentage = min(100.0, max(0.0, (total_weight_g / max_load) * 100.0))

        is_overloaded_calculated = total_weight_g >= OVERLOAD_WARNING_THRESHOLD
        final_is_overloaded = is_overloaded if is_overloaded is not None else is_overloaded_calculated

    else:
        # 기타 상태: 무게 0으로 설정
        weight_percentage = 0.0
        final_is_overloaded = False

    # --- 2. 조명 상태 계산 (전역 변수 사용) ---
    is_light_on = _is_light_on_status # 모니터링 쓰레드가 갱신한 전역 상태를 사용함

    # --- 3. 페이로드 구성 (DTO에 맞게 최소 필수 항목만 전송) ---
    return {
        "weight": round(weight_percentage, 1),
        "isOverloaded": final_is_overloaded,
        "isLightOn": is_light_on,
        "detectedObject": detected_obj,
        "status": status
    }

def send_data(payload: dict):
    """서버로 데이터를 전송합니다. (오류 수정 및 최소화 적용)"""
    try:
        # requests.post 호출 시 타임아웃을 짧게 설정하여 병목 현상 최소화
        requests.post(SERVER_URL, json=payload, timeout=0.3)
    except requests.exceptions.RequestException:
        # 통신 실패는 무시하고 프로그램 지속
        pass

# -------------------------------
# Main Loop
# -------------------------------
if __name__ == "__main__":
    # 카메라 인식 쓰레드 시작
    start_camera_process(0)
    t = threading.Thread(target=read_frames, daemon=True)
    t.start()

    # 여기서부터 모든 로직 구현을 하자!
    # 시작: 목표 설정부터(사과 -> 바나나 -> 브로콜리) 순으로 처리할거임
    target_order = [47, 46, 50]  # apple, banana, broccoli
    current_target_idx = 0

    # 객체 찾기
    # TODO: 객체 찾는 함수 구현, 사과와 차 모양이 동시에 있으면 그 곳이 시작점

    # 탐지 후 프레임 내에 찾는게 없으면 왼쪽으로 회전
    try:
        while not exit_flag:  # 무한 반복
            target_id = target_order[current_target_idx]
            main_target = TARGET_CLASSES[target_id]


            # PICK (들기)
            is_going_to_lift = True
            print("===========================================")
            print(f"Current target: {main_target}")
            print("===========================================")
            lifting_state = track_step(main_target, is_going_to_lift)

            print(f"놓기 여부 {lifting_state}")
            # PLACE (놓기) - 들기 성공했을 때만
            if lifting_state == True:
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