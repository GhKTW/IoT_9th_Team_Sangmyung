import spidev

# ---------------- SPI 초기화 ----------------
spi = None

def init_spi():
    global spi
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 1350000

def close_spi():
    if spi:
        spi.close()

# ---------------- ADC 읽기 ----------------
def read_adc(channel):
    if not 0 <= channel <= 7:
        raise ValueError("채널은 0~7 사이여야 합니다.")
    r = spi.xfer2([1, (8 + channel) << 4, 0])
    return ((r[1] & 3) << 8) + r[2]

def adc_to_voltage(adc_value, vref=3.3):
    return (adc_value / 1023.0) * vref

# ---------------- 거리 변환 ----------------
def voltage_to_distance_cm(voltage):
    if voltage < 0.25:
        return 15
    return min(15.0, max(2.0, (27.86 * (voltage ** -1.15)) / 10.0))

# ---------------- 반환용 함수 1: 거리값 3개 ----------------
def get_distance_values():
    """CH0 ~ CH2 거리 센서의 값을 cm로 반환"""
    channels = [0, 1, 2, 4]
    distances = []
    for ch in channels:
        adc_val = read_adc(ch)
        voltage = adc_to_voltage(adc_val)
        dist = voltage_to_distance_cm(voltage)
        distances.append(round(dist, 2))
    return distances  # 예: [5.32, 7.21, 12.44, 12.44]

# ---------------- 반환용 함수 2: 조도 센서 ----------------
def get_light_value(channel=3, vref=3.3):
    """CH3 조도 값을 % 단위로 반환"""
    adc_val = read_adc(channel)
    voltage = adc_to_voltage(adc_val, vref)
    percent = min(100.0, max(0.0, (voltage / vref) * 100.0))
    return round(percent, 1)
