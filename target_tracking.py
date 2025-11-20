#객체추적함수
from .movement import move_forward, turn_left, turn_right, stop, set_speed

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
