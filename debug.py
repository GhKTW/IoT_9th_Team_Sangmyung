from sensors import *
from movement import *

# lift_motor_up(1.6, 0.4)

# lift_motor_down(0.2, 0.4)

# move_forward(0.4, 0.4)

# turn_left(0.4, 0.5)

# turn_right(2.18, 0.5)
# setup_loadcell()

def lift():
    lifted_successful = False
    # TODO: 몇 초 동안 들어야 다 드는건지 확인하기
    for i in range(15): # 최대 10번 반복 들기 시도(10번 시도하면 다 들었다고 가정)
        lift_motor_up(0.2, 0.5)  # 속도 0.5로 들기
        print("lifting...")
        # 조금 들고 로드셀 값 읽기(한계 무게 초과인지를 계속 확인)
        weight = read_weights()
        total_weight = weight[0] + weight[1]
        print(total_weight)
        if total_weight >= 55000:  # 총 무게가 기준치 이하면 계속 들기
            # TODO: 무게 수치 확인 필요
            print("ffffffff")
            break
    else:
        lifted_successful = True
        print("sssssssss")



# lift()

# while True:
#     weight = read_weights()
#     total_weight = weight[0] + weight[1]
#     print(total_weight)