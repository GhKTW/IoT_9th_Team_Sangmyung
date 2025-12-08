import cv2
import subprocess
import shlex
import numpy as np
import threading
import time
import requests # [필수] 통신용
from ultralytics import YOLO
from sensors import *

# -------------------------------
# Initialize SPI for sensors
# -------------------------------
init_spi()
setup_loadcell()

# ==============================================================
#  통신 설정 및 함수
# ==============================================================
SERVER_URL = "http://192.168.137.3:8080/api/sensor/data"
MAX_LIFT_STOP_RAW_VALUE = 55000
OVERLOAD_WARNING_THRESHOLD = MAX_LIFT_STOP_RAW_VALUE * 0.8
_is_light_on_status = False
_last_status = "SEARCHING"

def get_sensor_state(detected_obj: str, status: str, total_weight_g: float | None = None, is_overloaded: bool | None = None) -> dict:
    global _is_light_on_status, _last_status

    #  조명 업데이트용("LIGHT_UPDATE") 호출이 아닐 때만 상태를 기록함
    # 즉, 메인 루프가 보내는 진짜 상태(LIFTING, MOVING 등)만 기억함
    if status != "LIGHT_UPDATE": 
        _last_status = status
    
    # 조명 업데이트일 경우, 계산을 위해 방금 기억해둔 상태(_last_status)를 임시로 사용
    current_calculation_status = _last_status if status == "LIGHT_UPDATE" else status

    # --- 1. 무게 및 과부하 계산 ---
    # 저장된 상태(_last_status)가 무게를 재야 하는 상태라면 무게를 읽음
    if current_calculation_status in ['LIFTING', 'WEIGHING', 'UNLOADING', 'OVERLOAD', 'TRANSPORTING']:
        if total_weight_g is None:
            weight = read_weights()
            total_weight_g = weight[0] + weight[1]
        
        max_load = MAX_LIFT_STOP_RAW_VALUE
        weight_percentage = min(100.0, max(0.0, (total_weight_g / max_load) * 100.0))
        is_overloaded_calculated = total_weight_g >= OVERLOAD_WARNING_THRESHOLD
        final_is_overloaded = is_overloaded if is_overloaded is not None else is_overloaded_calculated
    else:
        weight_percentage = 0.0
        final_is_overloaded = False

    return {
        "weight": round(weight_percentage, 1),
        "isOverloaded": final_is_overloaded,
        "isLightOn": _is_light_on_status,
        "detectedObject": detected_obj,
        "status": _last_status 
    }

def send_data(payload: dict):
    try:
        requests.post(SERVER_URL, json=payload, timeout=0.3)
    except requests.exceptions.RequestException:
        pass
# ==============================================================


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
detection_sequence = 0  # 객체 탐지 시퀀스 번호
process_every_n_frames = 10
frame_idx = 0
light_control_enabled = True  # 조도 센서 제어 활성화 플래그


# MOVING
FORWARD     = [1, 0, 1, 0]
BACKWARD    = [0, 1, 0, 1]
LEFT        = [1 ,0, 0, 1]
RIGHT       = [0, 1, 1, 0]
SNAKE_RIGHT = [0, 0, 1, 0]
SNAKE_LEFT  = [1, 0, 0, 0]

process = None

line_values = []

# ==============================================================
# =====================조도 센서 제어 START======================
# ==============================================================
def light_sensor_monitor():
    """조도 센서를 모니터링하고 조명을 자동으로 제어하는 쓰레드"""
    global exit_flag, light_control_enabled, _is_light_on_status

    print("조도 센서 모니터링 시작")

    while not exit_flag:
        if light_control_enabled:
            try:
                light_value = get_light_value()

                if light_value <= 10: # 어두움
                    if not _is_light_on_status:
                        lightOn()
                        _is_light_on_status = True
                        # [핵심] "LIGHT_UPDATE"라는 특수 키워드로 보냄
                        # -> get_sensor_state가 이걸 보고 "아, 상태는 바꾸지 말고 조명만 갱신하자"라고 판단함
                        send_data(get_sensor_state("none", "LIGHT_UPDATE"))
                        
                else: # 밝음
                    if _is_light_on_status:
                        lightOff()
                        _is_light_on_status = False
                        # [핵심] 꺼질 때도 동일하게 보냄
                        send_data(get_sensor_state("none", "LIGHT_UPDATE"))

            except Exception as e:
                print(f"조도 센서 읽기 오류: {e}")
                pass

        # 5초 대기
        time.sleep(5)

    print("조도 센서 모니터링 종료")

# ==============================================================
# =====================조도 센서 제어 END======================
# ==============================================================


# ==============================================================
# =====================이동 관련 START======================
# ==============================================================
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
# 왼쪽만 앞으로 해서 우회전
def turn_snake_r(duration: float | None = None):
    set_motor(SNAKE_RIGHT)
    time.sleep(duration)
    stop()
# 오른쪽만 앞으로 해서 좌회전
def turn_snake_l(duration: float | None = None):
    set_motor(SNAKE_LEFT)
    time.sleep(duration)
    stop()

# ==============================================================
# =========================이동 관련 END=========================
# ==============================================================


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
# YOLO 객체 검출 함수 (시퀀스 번호 포함)
# -------------------------------
def detect_object(image):
    global detection_sequence

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

    # 최신값 갱신 및 시퀀스 번호 증가 (락으로 동기화)
    with latest_centers_lock:
        latest_centers[:] = centers  # 리스트 내용 업데이트
        detection_sequence += 1
        current_seq = detection_sequence

    print(f"탐지 완료 [시퀀스 #{current_seq}]: {centers}")
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

# ==============================================================
# =====================타겟 트래킹 관련 START====================
# ==============================================================

FRAME_WIDTH_DEFAULT = 640 #가로가 320px /정중앙 x 좌표 160px
DEAD_ZONE = 28   # 중앙 ±20px

#카메라에서 얻은 객체 중심 x좌표를 오프셋으로 움직이는 함수
def track_step(target_class: str, is_going_to_lift: bool):
    print("물건 가지러 / 놓으러 가기 시작")
    search_count = 0
    max_search_attempts = 500000  # 최대 탐색 횟수
    last_turn_direction = None  # 마지막 회전 방향 저장 ('left' or 'right')
    last_processed_sequence = -1  # 마지막으로 처리한 시퀀스 번호

    while True:
        line_values = get_line_values()

        # 현재 시퀀스 번호와 탐지 결과를 안전하게 읽기
        with latest_centers_lock:
            current_sequence = detection_sequence
            current_centers = latest_centers[:]

        # 새로운 탐지 결과가 없으면 대기 (시퀀스 번호가 같으면 스킵)
        if current_sequence == last_processed_sequence:
            time.sleep(0.05)  # 짧은 대기 후 재확인
            continue

        # 새로운 탐지 결과만 처리
        last_processed_sequence = current_sequence
        print(f"새 탐지 결과 처리 시작 - 시퀀스: #{current_sequence}")

        # --- 트럭과 target_object를 찾기 ---
        target_object = next((obj for obj in current_centers if obj[0] == target_class), None)
        truck_object  = next((obj for obj in current_centers if obj[0] == TRUCK_CLASS_NAME), None)

        print(f"  Target: {target_object}, Truck: {truck_object}")  # 디버깅

        # ----------------------- CASE 1 : PICK MODE -----------------------
        if is_going_to_lift:
            if target_object is None:
                search_count += 1
                if search_count > max_search_attempts:
                    print("객체를 찾지 못함, 탐색 중단")
                    return False

                # 마지막 회전의 반대 방향으로 탐색
                if last_turn_direction == 'right':
                    print(f"  들기 모드, {target_class} 탐지 실패 - 좌회전 탐색 (우회전 했다가 놓침)")
                    turn_left(0.1)
                elif last_turn_direction == 'left':
                    print(f"  들기 모드, {target_class} 탐지 실패 - 우회전 탐색 (좌회전 했다가 놓침)")
                    turn_right(0.2)
                else:
                    print(f"  들기 모드, {target_class} 탐지 실패 - 좌회전 탐색 (기본)")
                    turn_left(0.1)

                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue

            if truck_object is not None:
                print(f"  들기 모드, {target_class}과 트럭이 동시에 감지됨 - 회피 동작")

                # 마지막 회전의 반대 방향으로 회피
                if last_turn_direction == 'right':
                    turn_left(0.1)
                elif last_turn_direction == 'left':
                    turn_right(0.1)
                else:
                    turn_left(0.1)

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

                # 마지막 회전의 반대 방향으로 탐색
                if last_turn_direction == 'right':
                    print(f"  놓기 모드, 객체 탐지 실패 - 좌회전 탐색 (우회전 했다가 놓침)")
                    turn_left(0.1)
                elif last_turn_direction == 'left':
                    print(f"  놓기 모드, 객체 탐지 실패 - 우회전 탐색 (좌회전 했다가 놓침)")
                    turn_right(0.1)
                else:
                    print(f"  놓기 모드, 객체 탐지 실패 - 좌회전 탐색 (기본)")
                    turn_left(0.1)

                time.sleep(0.4)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue

            # 두 객체의 x좌표 차이 확인
            x_diff = abs(target_object[1] - truck_object[1])
            print(f"  X 좌표 차이: {x_diff}")

            if x_diff > 70:
                search_count += 1
                if search_count > max_search_attempts:
                    print("정렬 실패, 탐색 중단")
                    return False

                print(f"  놓기 모드, 정렬 필요 (차이: {x_diff})")
                turn_left(0.1)
                last_turn_direction = 'left'  # 방향 저장
                time.sleep(0.2)
                if line_values[0] == 1 or line_values[1] == 1 or line_values[2] == 1:
                    print("라인 검출, 목적지 도착")
                    break
                continue
            else:
                search_count = 0
                target_x = truck_object[1]
                print(f"  객체 정렬 완료: truck at {target_x}")

        # ----------------------- MOVEMENT CONTROL -----------------------
        center_x = FRAME_WIDTH_DEFAULT // 2
        error = target_x - center_x
        scale = abs(error) / 320.0 * 0.3

        if abs(error) <= DEAD_ZONE:
            print("  찾아가는중... 전진")
            move_forward(0.3)
            last_turn_direction = None  # 전진 시 방향 초기화
            time.sleep(0.4)
        elif error < 0:
            print("  찾아가는중... 우회전")
            turn_right(scale)
            last_turn_direction = 'right'  # 우회전 방향 저장
            time.sleep(0.4)
        else:
            print("  찾아가는중... 좌회전")
            turn_left(scale)
            last_turn_direction = 'left'  # 좌회전 방향 저장
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
        # [통신] 도착했으니 'LIFTING' 보냄 (무게 0)
        send_data(get_sensor_state(target_class, "LIFTING", total_weight_g=0))

        #  target_class를 넣어줘야 어떤 물건인지 서버에 보냄
        success_lifting = attempt_lift(target_class)
        return success_lifting

    else:
        print("물건 놓기 시도")
        # 도착했으니 'UNLOADING' 보냄
        # 여기서 센서 읽어서 현재 무게 전송함
        send_data(get_sensor_state(target_class, "UNLOADING"))

        success_placing = attempt_place(target_class)
        return success_placing



# ==============================================================
# =====================타겟 트래킹 관련 END======================
# ==============================================================

# ==============================================================
# =====================물체 들어올리기 관련 START=================
# ==============================================================

def attempt_lift(target_name: str): # 이름만 받음
    print("물건 들기 시도 시작")
    # 이미 들 물체 앞에 있을 거임

    # 가운데 거리센서 값 읽어서 물체가 있는지 확인
    center_distance = get_distance_values()[1]  # 가운데 센서

    # 물건이 바로 앞에 없는 경우 추가
    ready_to_lift = False
    print(f"현재 내 앞 거리: {center_distance}")
    if center_distance > 8:  # 10cm 이내에 물체가 없으면
        print("가운데 거리센서, 물체 있는지 확인중...")
        for i in range(20):
            dist = get_distance_values()
            center_distance = dist[1]
            colision_detection = dist[2]
            print(f"  조금씩 전진 시도 #{i}, 거리: {center_distance}, {colision_detection}")
            if (center_distance <= 8 or colision_detection <= 12):
                print("물건 들기 준비 완료")
                ready_to_lift = True
                break
            else:
                move_forward(0.3)
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
        overweight = False
        for idx in range(100): # 최대 20번 반복 들기 시도
            lift_height = get_distance_values()[0]
            weight = read_weights()
            total_weight = weight[0] + weight[1]

            print(f"  lift_up #{idx}, weight: {total_weight}")

            lift_motor_up(0.1, 0.5)  # 속도 0.5로 들기


            if lift_height >= 7:
                print("물건 끝까지 들기 완료")
                lifted_successful = True
                stop()
                break
            elif total_weight >= 55000:
                print("하중 제한 초과, 들기 실패")
                #  과부하 알림
                send_data(get_sensor_state(target_name, "OVERLOAD", total_weight_g=total_weight, is_overloaded=True))
                lifted_successful = False
                overweight = True
                stop()
                break
            else:
                print("  들기 종료 조건 미충족, 계속 시도")
                continue

        weight = read_weights()
        total_weight = weight[0] + weight[1]
        if total_weight <= 1000:
            lifted_successful = False
            print("들기는 했는데 아무것도 없었음")

        if (not lifted_successful):
            # 한계 무게가 초과되었다면 다시 내리기
            lift_down_weight()

    # 일단 후진해서 180도 돌고, lift_successful 플래그에 따라 다음 동작 실행
    print("들기 시도 종료, 뒤로 가서 180도 회전")
    if (overweight == True):
        move_backward(0.7)
        stop()
    else:
        move_backward(0.7)  # 1초 후진
        turn_left(3)    # 2.18초 우회전 (대략 180도)
        stop()


    if (lifted_successful):
        print("물건 들기 성공, 들기 함수 종료")
        # [통신] 들었으니 운송 시작 (TRANSPORTING). 이때 멈춰있으니 정확한 무게 전송됨
        send_data(get_sensor_state(target_name, "TRANSPORTING"))
        return True
    elif(not lifted_successful):
        print("물건 들기 실패, 들기 함수 종료")
        # [통신] 실패했으니 다시 탐색 (SEARCHING, 무게 0)
        send_data(get_sensor_state(target_name, "SEARCHING", total_weight_g=0))
        return False


def attempt_place(target_name: str): # [필수] 이름만 받음
    # 물체 놓을 곳 바로 앞에 왔으니까, 내려놓기
    lift_down_weight()

    move_backward(0.7)  # 1초 후진
    turn_left(3)    # 2.18초 우회전 (대략 180도)
    stop()
    print("하차 끝")
    #  다 내렸으니 'ARRIVED' (무게 0)
    send_data(get_sensor_state("none", "ARRIVED", total_weight_g=0))
    return True


def lift_down_weight():
    placed_successful = False
    # 최대 30번 반복 내리기 시도
    for i in range(30):
        lift_motor_down(0.1, 0.5)  # 속도 0.5로 내리기
        print("  down...")
        # 조금 내리고 로드셀 값 읽기
        lift_height = get_distance_values()[0]
        print(f"  {lift_height}")
        if lift_height < 2.5:  # 총 무게가 기준치 이하면 내려놓기 완료
            print("내려놓기 끝")
            placed_successful = True
            break

    if placed_successful:
        print("내려놓기 성공")
    else:
        print("내려놓기 완료 (최대 시도 횟수 도달)")

# ===================================================================
# =====================물체 들어올리기 관련 END======================
# ===================================================================


# -------------------------------
# Main Loop
# -------------------------------
if __name__ == "__main__":
    # 카메라 인식 쓰레드 시작
    start_camera_process(0)
    t = threading.Thread(target=read_frames, daemon=True)
    t.start()

    # 조도 센서 모니터링 쓰레드 시작
    light_thread = threading.Thread(target=light_sensor_monitor, daemon=True)
    light_thread.start()

    # 여기서부터 모든 로직 구현을 하자!
    # 시작: 목표 설정부터(사과 -> 바나나 -> 브로콜리) 순으로 처리할거임
    target_order = [47, 46, 50]  # apple, banana, broccoli
    current_target_idx = 0

    # 객체 찾기

    # 탐지 후 프레임 내에 찾는게 없으면 왼쪽으로 회전
    try:
        while not exit_flag:  # 무한 반복
            target_id = target_order[current_target_idx]
            main_target = TARGET_CLASSES[target_id]

            # [통신] 탐색 시작
            send_data(get_sensor_state(main_target, "SEARCHING", total_weight_g=0))

            # PICK (들기)
            is_going_to_lift = True
            print("===========================================")
            print(f"Current target: {main_target}")
            print("===========================================")

            # [원상복구] 값 1개만 받음
            lifting_state = track_step(main_target, is_going_to_lift)

            print(f"놓기 여부 {lifting_state}")
            # PLACE (놓기) - 들기 성공했을 때만
            if lifting_state == True:
                is_going_to_lift = False
                # [원상복구] 무게 인자 삭제
                track_step(main_target, is_going_to_lift)

            # 다음 타겟으로 이동
            current_target_idx = (current_target_idx + 1) % len(target_order)


    except KeyboardInterrupt:
        print("프로그램 종료")
        # [통신] 종료 알림
        send_data(get_sensor_state("none", "ARRIVED", total_weight_g=0))
        exit_flag = True
    finally:
        stop()
        if process:
            process.terminate()