from gpiozero import DigitalOutputDevice, PWMOutputDevice
import time

# 사용할 GPIO 핀 번호 (BCM 기준)
pins = [19, 16, 26, 20]

# 방향 제어용 DigitalOutputDevice
outputs = [DigitalOutputDevice(pin) for pin in pins]

pins_for_lift_motor = [2, 3] 
outputs_lift = [DigitalOutputDevice(pin) for pin in pins_for_lift_motor]
ENA_lift = PWMOutputDevice(18)  


# 속도 제어용 PWM 핀 (ENA, ENB)
ENA = PWMOutputDevice(13)  # 모터 A 속도 제어
ENB = PWMOutputDevice(12)  # 모터 B 속도 제어

# 왼쪽 모터 앞
def leftMotorForward(speed):
    outputs[2].on()    # A1
    outputs[3].off()   # A2
    ENA.value = speed

# 왼쪽 모터 뒤
def leftMotorBackward(speed):
    outputs[2].off()   # A1
    outputs[3].on()    # A2
    ENA.value = speed

# 오른쪽 모터 앞
def rightMotorForward(speed):
    outputs[0].on()    # B1
    outputs[1].off()   # B2
    ENB.value = speed

# 오른쪽 모터 뒤
def rightMotorBackward(speed):
    outputs[0].off()   # B1
    outputs[1].on()    # B2
    ENB.value = speed

#양쪽 모터 모두 정지/ 부드러운 정지
def stop_all():
    # PWM 0으로
    ENA.value = 0.0
    ENB.value = 0.0
    ENA_lift = 0.0
    # 방향핀도 다 LOW로
    for o in outputs:
        o.off()
    for x in outputs_lift:
        x.off()
#브레이크 / 강한 제동
def brake_all():
    ENA.value = 1.0
    ENB.value = 1.0

    # 왼쪽 모터: 두 입력 LOW
    outputs[0].off()    # A1
    outputs[1].off()    # A2

    # 오른쪽 모터: 두 입력 LOW
    outputs[2].off()    # B1
    outputs[3].off()    # B2

def lift_motor_up(duaration: float, speed: float):
    ENA_lift.value = speed
    outputs_lift[0].off()    # LIFT1
    outputs_lift[1].on()   # LIFT2
    time.sleep(duaration)
    

def lift_motor_down(duaration: float, speed: float):
    ENA_lift.value = speed
    outputs_lift[0].on()   # LIFT1
    outputs_lift[1].off()    # LIFT2
    time.sleep(duaration)
    