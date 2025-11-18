from gpiozero import DigitalInputDevice
import time

# Initialize digital input devices
line = [
    DigitalInputDevice(14),
    DigitalInputDevice(15),
    DigitalInputDevice(23)
]

# while True:
#     # Read all values
#     value = [device.value for device in line]

#     # Print values
#     print(f"{value[0]} {value[1]} {value[2]}")
#     time.sleep(1)



def getLineValues():
    # Read all values
    value = [device.value for device in line]
