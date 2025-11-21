from sensors import *


# 객체 탐지를 통해 물체를 찾아 가다가 물체로 이어지는 선을 감지 한 직후 실행됨
# 선을 따라서 물체에 도달한 후 무게를 재 보고 들 지 말 지 결정하기
def lift_object(line = []):
    if line == {1, 0 ,0} or line == {1, 1, 0}:
        turn_left()
    elif line == {0, 0, 1} or line == {0, 1, 1}:
        turn_right()
    else:
        move_forward()

    stop()
    # weight = measure_weight()