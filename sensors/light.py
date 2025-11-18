from gpiozero import DigitalOutputDevice
import time

light = DigitalOutputDevice(21)

# 라이트 on
def lightOn():
    light.on()

# 라이트 off
def lightOff():
    light.off()