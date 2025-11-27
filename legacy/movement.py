#순수 모터 제어(이동) + 속도 제어 /
from sensors import *
import time

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
