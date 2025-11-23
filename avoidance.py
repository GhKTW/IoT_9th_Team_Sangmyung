from time import sleep
# 기존에 만들어둔 이동 모듈과 센서 모듈을 가져옵니다.
# movement.py와 sensors 폴더가 같은 경로(혹은 하위)에 있어야 합니다.
from movement import turn_left, turn_right, stop, move_backward
from sensors.distanceAndLightlevel import get_distance_values

# ==========================================
# ⚙️ 설정값 (상황에 맞춰 튜닝 필요)
# ==========================================
OBSTACLE_DIST_LIMIT = 15.0  # 15cm 이내면 장애물로 인식
AVOID_SPEED = 0.6           # 회피 기동 속도
AVOID_TIME = 0.5            # 회피(회전) 지속 시간 (초)

# ==========================================
# 🛡️ 장애물 감지 및 회피 함수
# ==========================================
def check_and_avoid_obstacle():
    """
    좌/우 거리 센서를 확인하여 장애물이 있으면 즉시 회피 기동을 수행합니다.

    Returns:
        bool: 회피 동작을 수행했으면 True, 아니면 False
    """
    # 거리 센서 값 읽기 [왼쪽, 중앙, 오른쪽]
    # (실제 센서 연결 순서에 따라 인덱스 0, 2가 바뀌었는지 확인 필요)
    try:
        dists = get_distance_values()
    except Exception as e:
        print(f"센서 오류: {e}")
        return False

    left_dist = dists[0]   # 왼쪽 센서
    center_dist = dists[1] # 중앙 센서
    right_dist = dists[2]  # 오른쪽 센서

    is_avoided = False

    # 1. 왼쪽 장애물 감지 -> 오른쪽으로 회피
    if left_dist < OBSTACLE_DIST_LIMIT and left_dist > 0: # 0인 경우는 노이즈일 수 있으므로 제외
        print(f"⚠️ 왼쪽 장애물 감지({left_dist}cm)! 우회전으로 회피합니다.")

        # 안전을 위해 살짝 뒤로 갔다가 회전 (공간 확보)
        move_backward(0.3, AVOID_SPEED)
        turn_right(AVOID_TIME, AVOID_SPEED)
        is_avoided = True

    # 2. 오른쪽 장애물 감지 -> 왼쪽으로 회피
    elif right_dist < OBSTACLE_DIST_LIMIT and right_dist > 0:
        print(f"⚠️ 오른쪽 장애물 감지({right_dist}cm)! 좌회전으로 회피합니다.")

        move_backward(0.3, AVOID_SPEED)
        turn_left(AVOID_TIME, AVOID_SPEED)
        is_avoided = True

    # 3. 전방(중앙) 장애물 감지 (이동 중일 때만)
    # elif center_dist < 10.0 and center_dist > 0:
    #     print("⚠️ 전방 막힘! 후진 후 회전")
    #     move_backward(0.5, AVOID_SPEED)
    #     turn_left(0.5, AVOID_SPEED)
    #     is_avoided = True

    if is_avoided:
        stop() # 회피 후 정지 상태로 만듦 (다음 명령 대기)

    return is_avoided