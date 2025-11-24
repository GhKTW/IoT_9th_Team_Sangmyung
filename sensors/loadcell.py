import time
import RPi.GPIO as GPIO
from hx711py.hx711 import HX711

hx1 = HX711(5, 6)
hx2 = HX711(22, 27)

def setup_loadcell():
    hx1.set_reading_format("MSB", "MSB")
    hx1.set_reference_unit(1)
    hx1.reset()
    hx1.tare()

    hx2.set_reading_format("MSB", "MSB")
    hx2.set_reference_unit(1)
    hx2.reset()
    hx2.tare()

def read_weights():
    weight1 = hx1.get_weight(1)
    weight2 = hx2.get_weight(1)
    return weight1, weight2

def cleanup_loadcell():
    GPIO.cleanup()