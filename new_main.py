import cv2
import subprocess
import shlex
import numpy as np
import threading
import time
import requests # requests 라이브러리 추가
from ultralytics import YOLO
from sensors import *

# ==========================================
# ⚡ 서버 통신 설정
# ==========================================
SERVER_URL = "http://localhost:8080/api/sensor/data"

# 로드셀 무게 기준 (raw value: gram)
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
TARGET_CLASSES = {47: "apple", 46: "banana", 50: "broccoli", 7: "truck"}
TRUCK_CLASS_NAME = "truck"

# -------------------------------
# Global State
# -------------------------------
exit_flag = False
latest_centers = []
latest_centers_lock = threading.Lock()
process_every_n_frames = 15
frame_idx = 0

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
# Helper function to send sensor data
# -------------------------------
def get_sensor_state(detected_obj: str, status: str, total_weight_g: float | None = None, is_overloaded: bool | None = None) -> dict:
    """현재 센서 상태를 읽어 서버 전송용 딕셔너리를 반환합니다."""
    # 센서 값 읽기
    distance_values = get_distance_values()
    light_level = get_light_level()

    if total_weight_g is None:
        weight = read_weights()
        total_weight_g = weight[0] + weight[1]

    # 무게 백분율 계산 (최대 55000이 100%가 되도록)
    max_load = MAX_LIFT_STOP_RAW_VALUE # 55000
    weight_percentage = min(100.0, max(0.0, (total_weight_g / max_load) * 100.0))

    # 과부하 상태 결정 (80% 기준)
    if is_overloaded is None:
        is_overloaded = total_weight_g >= OVERLOAD_WARNING_THRESHOLD

    # 라이트 상태 결정 (임의 로직: 광량 100 이하일 때 켜짐)
    is_light_on = light_level < 100

    return {
        "distance": round(distance_values[1], 1), # 가운데 거리센서 (cm)
        "lightLevel": light_level,
        "weight": round(weight_percentage, 1), # 백분율로 변환하여 전송
        "isOverloaded": is_overloaded,
        "isLightOn": is_light_on,
        "detectedObject": detected_obj,
        "status": status
    }

def send_data(payload: dict):
    """서버로 데이터를 전송합니다."""
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=0.5)
        # print(f"📡 전송: {payload['status']} | 물체: {payload['detectedObject']} | 무게: {payload['weight']}% | 응답: {response.status_code}")
    except requests.exceptions.RequestException as e:
        # print(f"❌ 전송 실패: {e}")
        pass # 통신 실패는 무시하고 프로그램 지속

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
        # print(f"Detected: {latest_centers}") # 디버깅용
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
                        # read_frames는 주기적인 이미지 처리만 전담하고,
                        # 상태 전송은 메인 로직(track_step, lift 등)에서 수행하여 중복 방지
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

#카메라에서 얻은 객체 중심 x좌표를 오프셋으로 움직이는 함수
def track_step(target_class: str, is_going_to_lift: bool):
    print("물건 가지러 / 놓으러 가기 시작")

    # --- 상태 전송: 초기 시작 (SEARCHING/TRANSPORTING) ---
    current_status = "SEARCHING" if is_going_to_lift else "TRANSPORTING"
    payload = get_sensor_state(target_class, current_status, is_overloaded=False)
    send_data(payload)

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

        # ----------------------- CASE 1 : PICK MODE -----------------------
        if is_going_to_lift:
            current_status = "SEARCHING"
            current_target_name = target_class

            if target_object is None:
                search_count += 1
                if search_count > max_search_attempts:
                    print("객체를 찾지 못함, 탐색 중단")
                    send_data(get_sensor_state("none", "ERROR", is_overloaded=False))
                    return False

                print(f"들기 모드, {target_class} 탐지 실패 - 좌회전 탐색")
                turn_left(0.4)
                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break

                payload = get_sensor_state(current_target_name, current_status, is_overloaded=False)
                send_data(payload)
                continue

            current_status = "APPROACHING"

            if truck_object is not None:
                print(f"들기 모드, {target_class}과 트럭이 동시에 감지됨 - 회피 동작")
                turn_left(0.4)
                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break

                payload = get_sensor_state(current_target_name, current_status, is_overloaded=False)
                send_data(payload)
                continue

            search_count = 0
            target_x = target_object[1]

        # ----------------------- CASE 2 : PLACE MODE -----------------------
        else:
            current_status = "TRANSPORTING"
            current_target_name = target_class

            if target_object is None or truck_object is None:
                search_count += 1
                if search_count > max_search_attempts:
                    print("목적지를 찾지 못함, 탐색 중단")
                    send_data(get_sensor_state(target_class, "ERROR", is_overloaded=None))
                    return False

                print(f"놓기 모드, 객체 탐지 실패")
                turn_left(0.4)
                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break

                payload = get_sensor_state(current_target_name, current_status, is_overloaded=None)
                send_data(payload)
                continue

            # 두 객체의 x좌표 차이 확인
            x_diff = abs(target_object[1] - truck_object[1])

            if x_diff > 70:
                search_count += 1
                if search_count > max_search_attempts:
                    print("정렬 실패, 탐색 중단")
                    send_data(get_sensor_state(target_class, "ERROR", is_overloaded=None))
                    return False

                print(f"놓기 모드, 정렬 필요 (차이: {x_diff})")
                turn_left(0.2)
                time.sleep(0.2)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break

                payload = get_sensor_state(current_target_name, current_status, is_overloaded=None)
                send_data(payload)
                continue
            else:
                search_count = 0
                target_x = truck_object[1]

        # ----------------------- MOVEMENT CONTROL -----------------------
        center_x = FRAME_WIDTH_DEFAULT // 2
        error = target_x - center_x
        scale = abs(error) / 320.0 * 0.45 + 0.05

        current_status = "APPROACHING" if is_going_to_lift else "TRANSPORTING"

        if abs(error) <= DEAD_ZONE:
            # print("찾아가는중... 전진")
            move_forward(0.3)
            time.sleep(0.4)
        elif error < 0:
            # print("찾아가는중... 우회전")
            turn_right(scale)
            time.sleep(0.4)
        else:
            # print("찾아가는중... 좌회전")
            turn_left(scale)
            time.sleep(0.4)

        # 움직인 후 상태 전송
        payload = get_sensor_state(current_target_name, current_status, is_overloaded=None)
        send_data(payload)

        time.sleep(0.05)  # 안정화 대기

        # --------- EXIT CONDITION: line detected ---------
        if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
            print("라인 검출, 목적지 도착")
            break


    # ----------------------- FINAL ACTION -----------------------
    stop()

    # --- 상태 전송: 목적지 도착 ---
    payload = get_sensor_state(target_class, "ARRIVED", is_overloaded=None)
    send_data(payload)

    if is_going_to_lift:
        print("물건 들기 시도")
        success_lifting = attempt_lift(target_class)
        return success_lifting

    else:
        print("물건 놓기 시도")
        success_placing = attempt_place(target_class)
        return success_placing



# =========================================================
# =====================타겟 트래킹 관련 END======================
# =========================================================

# =========================================================
# =====================물체 들어올리기 관련 START======================
# =========================================================

def attempt_lift(target_class: str):
    print("물건 들기 시도 시작")

    # --- 상태 전송: LIFTING 시작 ---
    payload = get_sensor_state(target_class, "LIFTING", is_overloaded=False)
    send_data(payload)

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
                # 전진 중 상태 전송
                payload = get_sensor_state(target_class, "LIFTING", is_overloaded=False)
                send_data(payload)
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
            # print(f"lift_up #{idx}")
            lift_height = get_distance_values()[0]
            weight = read_weights()
            total_weight = weight[0] + weight[1]

            is_overloaded = total_weight >= OVERLOAD_WARNING_THRESHOLD # 80% 기준 (44000)

            lift_motor_up(0.1, 0.5)  # 속도 0.5로 들기

            # --- 상태 전송: LIFTING 중 ---
            current_status = "LIFTING"
            if is_overloaded:
                current_status = "OVERLOAD"

            payload = get_sensor_state(target_class, current_status, total_weight_g=total_weight, is_overloaded=is_overloaded)
            send_data(payload)


            if lift_height >= 7:
                print("물건 끝까지 들기 완료")
                lifted_successful = True
                stop()

                # --- 상태 전송: WEIGHING (들기 완료) ---
                payload = get_sensor_state(target_class, "WEIGHING", total_weight_g=total_weight, is_overloaded=is_overloaded)
                send_data(payload)
                time.sleep(1)

                break
            elif total_weight >= MAX_LIFT_STOP_RAW_VALUE: # 하드 스톱 기준 (55000)
                print("하중 제한 초과, 들기 실패")
                lifted_successful = False
                stop()

                # --- 상태 전송: OVERLOAD (하드 스톱) ---
                payload = get_sensor_state(target_class, "OVERLOAD", total_weight_g=total_weight, is_overloaded=True)
                send_data(payload)
                time.sleep(1)

                break
            else:
                # print("들기 종료 조건 미충족, 계속 시도")
                continue

        if (not lifted_successful):
            # 한계 무게가 초과되었다면 다시 내리기
            lift_down_weight(target_class, is_overloaded=True)

    # 일단 후진해서 180도 돌고, lift_successful 플래그에 따라 다음 동작 실행
    print("들기 시도 종료, 뒤로 가서 180도 회전")
    move_backward(0.6)  # 1초 후진
    turn_left(4)    # 2.18초 우회전 (대략 180도)
    stop()

    # --- 상태 전송: 이동 완료 후 STANDBY/TRANSPORTING ---
    if lifted_successful:
        status_after_rotation = "TRANSPORTING"
    else:
        status_after_rotation = "STANDBY"

    payload = get_sensor_state(target_class, status_after_rotation, is_overloaded=False)
    send_data(payload)


    if (lifted_successful):
        print("물건 들기 성공, 들기 함수 종료")
        return True
    elif(not lifted_successful):
        print("물건 들기 실패, 들기 함수 종료")
        return False


def attempt_place(target_class: str):
    # 물체 놓을 곳 바로 앞에 왔으니까, 내려놓기
    print("물건 놓기 시도")
    # --- 상태 전송: UNLOADING 시작 ---
    weight = read_weights()
    total_weight = weight[0] + weight[1]
    is_overloaded = total_weight >= OVERLOAD_WARNING_THRESHOLD
    payload = get_sensor_state(target_class, "UNLOADING", total_weight_g=total_weight, is_overloaded=is_overloaded)
    send_data(payload)

    lift_down_weight(target_class, is_overloaded=is_overloaded)

    move_backward(0.7)  # 1초 후진
    turn_left(4)    # 2.18초 우회전 (대략 180도)
    stop()

    # --- 상태 전송: 완료 (ARRIVED) ---
    payload = get_sensor_state("none", "ARRIVED", is_overloaded=False)
    send_data(payload)

    print("하차 끝")
    return True


def lift_down_weight(target_class: str, is_overloaded: bool = False):
    placed_successful = False

    current_status = "OVERLOAD_RECOVERY" if is_overloaded else "UNLOADING"

    # 최대 30번 반복 내리기 시도
    for i in range(30):
        lift_motor_down(0.1, 0.5)  # 속도 0.5로 내리기
        # print("down...")
        # 조금 내리고 로드셀 값 읽기
        lift_height = get_distance_values()[0]
        weight = read_weights()
        total_weight = weight[0] + weight[1]
        # print(total_weight)

        # --- 상태 전송: UNLOADING 중 ---
        payload = get_sensor_state(target_class, current_status, total_weight_g=total_weight, is_overloaded=is_overloaded)
        send_data(payload)

        if total_weight <= 5000 or lift_height < 2.5:  # 총 무게가 기준치 이하면 내려놓기 완료
            print("내려놓기 끝")
            placed_successful = True
            break

    if placed_successful:
        print("내려놓기 성공")
        # --- 상태 전송: 무게가 0에 가까워짐 ---
        payload = get_sensor_state("none", "UNLOADING_COMPLETE", total_weight_g=total_weight, is_overloaded=False)
        send_data(payload)
    else:
        print("내려놓기 완료 (최대 시도 횟수 도달)")
        # --- 상태 전송: 최대 시도 후 완료 ---
        payload = get_sensor_state("none", "UNLOADING_COMPLETE", total_weight_g=total_weight, is_overloaded=False)
        send_data(payload)

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
    # 시작: 목표 설정부터(사과 -> 바나나 -> 브로콜리) 순으로 처리할거임
    target_order = [47, 46, 50]  # apple, banana, broccoli
    current_target_idx = 0

    # --- 상태 전송: 초기 STANDBY ---
    initial_payload = get_sensor_state("none", "STANDBY", is_overloaded=False)
    send_data(initial_payload)

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
        # --- 상태 전송: 종료 ---
        final_payload = get_sensor_state("none", "SHUTDOWN", is_overloaded=False)
        send_data(final_payload)