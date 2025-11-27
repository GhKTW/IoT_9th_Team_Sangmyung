import requests
import time
import random

# ==========================================
# ⚡ 설정 (내 컴퓨터에서 서버로 쏘는 거라 localhost)
# ==========================================
SERVER_URL = "http://localhost:8080/api/sensor/data"

# 과일 목록 (랜덤 선택용) - grape -> orange 변경 -> broccoli 변경
FRUITS = ["apple", "banana", "broccoli"]

def send_data(dist, light, weight, is_overloaded, light_on, obj, status):
    payload = {
        "distance": dist,
        "lightLevel": light,
        "weight": weight,
        "isOverloaded": is_overloaded,
        "isLightOn": light_on,
        "detectedObject": obj,
        "status": status
    }
    try:
        response = requests.post(SERVER_URL, json=payload)
        print(f"📡 전송: {status} | 물체: {obj} | 응답: {response.status_code}")
    except Exception as e:
        print(f"❌ 전송 실패: {e}")

def run_scenario():
    print("🚀 가상 지게차 시뮬레이션을 시작합니다!")

    while True:
        # 1. 이번엔 어떤 과일을 옮길까?
        target_fruit = random.choice(FRUITS)
        print(f"\n🎯 [시나리오 시작] 목표: {target_fruit}")

        # --- [단계 1] 탐색 (SEARCHING) ---
        for _ in range(3):
            send_data(150, 300, 0, False, False, "none", "SEARCHING")
            time.sleep(1)

        # --- [단계 2] 접근 & 발견 (APPROACHING) ---
        for i in range(3):
            dist = 100 - (i * 30) # 거리가 줄어듦
            send_data(dist, 300, 0, False, True, target_fruit, "APPROACHING")
            time.sleep(1)

        # --- [단계 3] 적재 (LIFTING) ---
        for i in range(4):
            weight = i * 0.5 # 무게가 서서히 늘어남
            send_data(10, 200, weight, False, True, target_fruit, "LIFTING")
            time.sleep(1)

        # --- [단계 4] 무게 측정 (WEIGHING) ---
        final_weight = round(random.uniform(2.0, 4.5), 1)
        send_data(10, 200, final_weight, False, True, target_fruit, "WEIGHING")
        time.sleep(2)

        # (과적 시뮬레이션 확률 10%)
        if random.random() < 0.1:
            print("⚠️ 과적 발생 시뮬레이션!")
            for _ in range(5):
                send_data(10, 200, 8.5, True, True, target_fruit, "OVERLOAD")
                time.sleep(1)
            continue

            # --- [단계 5] 이동 (TRANSPORTING) ---
        print("🚚 이동 중...")
        for _ in range(5):
            light_level = random.randint(50, 150)
            is_light_on = light_level < 100
            send_data(50, light_level, final_weight, False, is_light_on, target_fruit, "TRANSPORTING")
            time.sleep(1)

        # --- [단계 6] 하역 (UNLOADING) ---
        for i in range(4):
            w = final_weight - (i * 0.8)
            if w < 0: w = 0
            send_data(20, 300, round(w, 1), False, False, target_fruit, "UNLOADING")
            time.sleep(1)

        # --- [단계 7] 완료 (ARRIVED) ---
        send_data(20, 300, 0, False, False, "none", "ARRIVED")
        time.sleep(2)

        print("✅ 운송 완료! 다음 작업 준비 중...")
        time.sleep(1)

if __name__ == "__main__":
    run_scenario()