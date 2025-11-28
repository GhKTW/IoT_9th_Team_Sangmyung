from sensors import *

init_spi()

while True:
    dist = get_distance_values()[0]
    print(dist)
    if dist <= 2.5:
        break
    else:
        lift_motor_down(0.2, 0.5)

# while True:
#     lift_motor_up(0.2, 1)