from gpiozero import DigitalInputDevice

# Initialize digital input devices
line = [
    DigitalInputDevice(14),
    DigitalInputDevice(15),
    DigitalInputDevice(23)
]

def getLineValues():
    # Read all values
    return [device.value for device in line]
