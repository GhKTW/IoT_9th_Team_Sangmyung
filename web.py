# --- 백엔드 통신 함수 ---
BACKEND_BASE_URL = "http://127.0.0.1:8080"  # 백엔드 기본 URL

def send_to_backend(endpoint: str, data_dict: dict):
    """
    백엔드로 데이터를 전송하는 함수
    
    Args:
        endpoint (str): API 엔드포인트 경로 (예: "/api/robot-state", "/api/sensor-data")
        data_dict (dict): 전송할 데이터 딕셔너리
    
    Returns:
        bool: 성공 시 True, 실패 시 False
    """
    url = f"{BACKEND_BASE_URL}{endpoint}"
    
    try:
        response = requests.post(
            url,
            json=data_dict,
            timeout=3  # 3초 타임아웃
        )
        
        if response.status_code == 200:
            print(f"[Backend] {endpoint} - Data sent: {data_dict}")
            return True
        else:
            print(f"[Backend] {endpoint} - Failed ({response.status_code}): {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"[Backend Error] {endpoint} - Request timeout")
        return False
    except requests.exceptions.ConnectionError:
        print(f"[Backend Error] {endpoint} - Connection failed")
        return False
    except Exception as e:
        print(f"[Backend Error] {endpoint} - {e}")
        return False


# --- 상태별 전송 함수들 ---

def send_robot_state(state: str, target: str = None, additional_data: dict = None):
    """로봇의 현재 상태를 전송"""
    data = {
        "state": state,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    if target:
        data["target"] = target
    if additional_data:
        data.update(additional_data)
    
    return send_to_backend("/api/robot-state", data)


def send_sensor_data(weight: float, distance: list, line_values: list):
    """센서 데이터를 전송"""
    data = {
        "weight": round(weight, 2),
        "distances": distance,
        "line_values": line_values,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    return send_to_backend("/api/sensor-data", data)


def send_detection_data(detected_objects: list):
    """객체 검출 결과를 전송"""
    data = {
        "detected_objects": detected_objects,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    return send_to_backend("/api/detection", data)


def send_task_result(task: str, success: bool, target: str = None, reason: str = None):
    """작업 결과를 전송"""
    data = {
        "task": task,
        "success": success,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    if target:
        data["target"] = target
    if reason:
        data["reason"] = reason
    
    return send_to_backend("/api/task-result", data)


# --- 사용 예시 ---

# 1. detect_object 함수에서 검출 결과 전송
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

    with latest_centers_lock:
        global latest_centers
        latest_centers = centers[:]
    
    # 백엔드로 검출 결과 전송
    send_detection_data(centers)
    
    return centers


# 2. attempt_lift 함수에서 들기 시작/결과 전송
def attempt_lift():
    send_robot_state("lifting_started", main_target)
    
    # ... (기존 들기 로직) ...
    
    if lifted_successful:
        send_task_result("lift", True, main_target)
        return True
    else:
        send_task_result("lift", False, main_target, "weight_exceeded or no_object")
        return False


# 3. attempt_place 함수에서 놓기 시작/결과 전송
def attempt_place():
    send_robot_state("placing_started", main_target)
    
    lift_down_weight()
    move_backward(0.7)
    turn_left(4)
    stop()
    
    send_task_result("place", True, main_target)
    return True


# 4. main loop에서 타겟 변경 시 전송
# main loop 예시:
# current_target_idx = 0
# target_id = target_order[current_target_idx]
# main_target = TARGET_CLASSES[target_id]
# send_robot_state("searching", main_target)