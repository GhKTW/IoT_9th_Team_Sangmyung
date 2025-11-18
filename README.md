# 사물인터넷 9조 (프로젝트 문서) (코파일럿이 만들어 줬어요)

이 문서는 프로젝트에 포함된 센서 관련 함수들의 사용법과 인자 설명, 그리고 `yoloDetection.py`가 하는 일을 정리합니다.

## 요약
- `sensors/` 폴더: SPI 기반 ADC(거리/조도), 라인트레이서 입력, 라이트(출력), 모터 제어 함수들을 포함합니다.
- `yoloDetection.py`: 카메라 스트림을 읽어 YOLOv8 모델로 과일을 탐지하고, 탐지 결과를 UDP로 송신하며 화면에 표시합니다(이건 구현예정).

---

## 공통 전제(반드시 읽을 것)
- Raspberry Pi + libcamera 환경을 기준으로 작성되어 있습니다.
- 필요한 패키지(예시): `spidev`, `gpiozero`, `ultralytics`, `opencv-python`, `numpy` 등.
- 센서 관련 함수는 SPI 초기화(`init_spi`)를 먼저 호출해야 합니다. 사용이 끝나면 `close_spi()`로 닫아 주세요.

---

### sensors/distanceAndLightlevel.py
주요 역할: SPI로 MCP3008(예: ADC)을 읽어 거리 센서(아날로그)와 조도(아날로그)를 처리합니다.

함수 목록 및 설명:
- init_spi()
	- 설명: SPI 인터페이스를 초기화합니다. `spidev.SpiDev()`를 사용하여 (bus=0, device=0)로 엽니다.
	- 인자: 없음
	- 반환: 없음
	- 사용법: 프로그램 시작 시 반드시 호출해야 합니다.

- close_spi()
	- 설명: 열려 있는 SPI를 닫습니다.
	- 인자: 없음
	- 반환: 없음

- read_adc(channel)
	- 설명: 지정한 ADC 채널(0~7)의 raw ADC 값을 읽습니다.
	- 인자: channel (int) — 0 이상 7 이하
	- 반환: int (0~1023)
	- 예외: 채널 범위 밖이면 ValueError 발생

- adc_to_voltage(adc_value, vref=3.3)
	- 설명: ADC 값을 전압으로 변환합니다.
	- 인자: adc_value (int), vref (float, 기본 3.3V)
	- 반환: float (전압, V)

- voltage_to_distance_cm(voltage)
	- 설명: 센서 전압을 거리(cm)로 근사 변환합니다. (프로젝트에 맞춘 경험적 포뮬러 사용)
	- 인자: voltage (float)
	- 반환: float (cm)
	- 주의: voltage < 0.25V이면 0을 반환합니다. 반환 범위는 약 2~15cm로 클램프됩니다.

- get_distance_values()
	- 설명: CH0~CH2(채널 0,1,2)에서 읽은 거리 값을 cm 단위로 리스트로 반환합니다.
	- 인자: 없음
	- 반환: list[float] (예: [5.32, 7.21, 12.44])
	- 사용 예:
		```python
		from sensors import init_spi, get_distance_values, close_spi
		init_spi()
		distances = get_distance_values()
		print(distances)
		close_spi()
		```

- get_light_value(channel=3, vref=3.3)
	- 설명: 지정 채널(기본 CH3)의 조도 값을 백분율(%)로 반환합니다.
	- 인자: channel (int, 기본 3), vref (float, 기본 3.3)
	- 반환: float (예: 45.3)
	- 사용 예:
		```python
		from sensors import init_spi, get_light_value
		init_spi()
		light_percent = get_light_value()  # 기본 채널 사용
		print(f"조도: {light_percent}%")
		close_spi()
		```

주의사항:
- `init_spi()`를 호출하지 않으면 `read_adc`가 실패하거나 `spi`가 None인 상태로 예외가 발생할 수 있습니다.

---

### sensors/light.py
GPIO로 라이트(출력)를 제어합니다. `gpiozero.DigitalOutputDevice`를 사용합니다.

- lightOn()
	- 설명: 라이트(GPIO21)를 ON으로 설정합니다.
	- 인자: 없음

- lightOff()
	- 설명: 라이트를 OFF로 설정합니다.
	- 인자: 없음

사용 예:
```python
from sensors import lightOn, lightOff
lightOn()
time.sleep(1)
lightOff()
```

---

### sensors/lintracer.py
라인 트레이싱용 디지털 입력(예: 라인트레이서 센서)에서 값을 읽습니다.

현 상태:
- 파일에는 `line = [DigitalInputDevice(14), DigitalInputDevice(15), DigitalInputDevice(23)]`로 3개의 입력을 초기화합니다.
- 정의된 함수 이름은 `getLineValues()`이며, 내부에서 `value = [device.value for device in line]`을 만들지만 현재 `return` 문이 없습니다. 즉, 호출해도 값을 반환하지 않습니다.

권장 (문서 목적) API:
- getLineValues()
	- 설명: 3개 라인 센서의 디지털 값을 리스트로 반환합니다. 값은 0.0 또는 1.0 (gpiozero의 `value`) 일 수 있습니다.
	- 사용 예:
		```python
		from sensors.lintracer import getLineValues  
		values = getLineValues()
		print(values)  # 예: [1.0, 0.0, 1.0]
		```

---

### sensors/motor.py
모터 제어용 함수들입니다. `gpiozero.DigitalOutputDevice`와 `PWMOutputDevice`를 사용해 방향 및 속도를 제어합니다.

핀 구성(파일 내부):
- 방향 제어 핀: [19, 16, 26, 20]
- PWM(속도) 제어: ENA = PWMOutputDevice(13), ENB = PWMOutputDevice(12)

함수:
- leftMotorForward(speed)
	- 설명: 왼쪽 모터를 전진(앞)으로 돌립니다.
	- 인자: speed (0.0~1.0) — PWM 값

- leftMotorBackward(speed)
	- 설명: 왼쪽 모터를 후진(뒤)으로 돌립니다.
	- 인자: speed (0.0~1.0)

- rightMotorForward(speed)
	- 설명: 오른쪽 모터 전진
	- 인자: speed (0.0~1.0)

- rightMotorBackward(speed)
	- 설명: 오른쪽 모터 후진
	- 인자: speed (0.0~1.0)

사용 예:
```python
from sensors import leftMotorForward, rightMotorForward, leftMotorBackward
leftMotorForward(0.6)
rightMotorForward(0.6)
time.sleep(1)
leftMotorBackward(0.5)
```

주의:
- 0.3 밑으로는 동작하지 않음
- 둘 다 돌렸는데 하나만 돌아가면 전원 부족

---

## yoloDetection.py 설명

yoloDetection.py는 아래 기능을 수행합니다:
그리고 아마 얘를 메인으로 해서 기능들을 이것저것 붙일 듯

- SPI 초기화: `init_spi()`를 호출해 센서(ADC)를 초기화합니다.
- YOLOv8 모델 로드: `ultralytics.YOLO('yolov8n.pt')`를 사용해 사전학습된 모델을 로드합니다. (요구: `yolov8n.pt` 파일이 프로젝트 루트 또는 지정 경로에 있어야 함)
- libcamera를 이용한 MJPEG 스트림 수신: `libcamera-vid`를 subprocess로 호출하여 stdout으로 MJPEG 스트림을 받습니다.
- 프레임 디코딩: stdout에서 JPEG 바이트를 찾아 OpenCV로 디코딩합니다.
- 객체 탐지: `model(image, classes=list(TARGET_CLASSES.keys()))`로 지정한 클래스(예: 사과, 바나나, 오렌지)만 탐지합니다.
- 탐지 결과 시각화: 바운딩 박스와 라벨을 이미지에 그림.
- UDP 전송: 탐지된 각 객체의 중심 좌표를 `UDP_IP:UDP_PORT`로 전송합니다. 전송 메시지 형식: `"{이름}:{x_center},{y_center}"` (예: `apple:160,120`)
- 스레딩: 카메라 스트림 읽기와 모델 추론/화면 출력은 별도 스레드에서 돌립니다.

주요 전역 설정/상수:
- TARGET_CLASSES: YOLO 클래스 id를 프로젝트에서 사용하기 쉽게 문자열로 매핑. 예: {47: 'apple', 46:'banana', 49:'orange'}
- process_every_n_frames: 몇 프레임마다 모델을 실행할지 결정(기본 15)
- UDP_IP, UDP_PORT: 탐지 결과를 전송할 대상(기본값 `192.168.0.10:5005`)

실행 요구사항 및 주의사항:
- libcamera 설치 및 `libcamera-vid` 사용 가능해야 합니다. (Raspberry Pi OS에서 기본 제공되거나 apt로 설치)
- `yolov8n.pt` 모델 파일이 필요합니다. ultralytics 패키지를 설치하세요(`pip install ultralytics`).
- OpenCV, numpy 필요(`pip install opencv-python numpy`).
- 프로그램은 ESC(키 코드 27)로 창을 닫아 종료 신호를 보내고 `exit_flag`를 통해 루프를 종료합니다.
- 종료 시 `process.terminate()`로 외부 프로세스를 정리합니다.

예상 동작(간단):
1. `python yoloDetection.py` 로 실행
2. 카메라(카메라 인덱스 0)를 libcamera로 열고 프레임을 읽음
3. 지정된 간격(예: 15프레임)마다 YOLO로 탐지 수행
4. 탐지된 객체 중심 좌표를 UDP로 송신((((아직 아님))))
5. 탐지 영상은 OpenCV 창에 표시되며 ESC로 종료

데모용 UDP 메시지 예:
- `apple:160,120` — 프레임 좌표계에서 (160,120)에 사과가 검출됨(((((아직 아님)))))

---

## 설치 및 실행 팁

이 밑은 아마 신경 쓸 필요 없을듯

권장 패키지(일반):
```
pip install spidev gpiozero ultralytics opencv-python numpy
```

실행 예:
```
python yoloDetection.py
```

하드웨어/환경 관련 체크리스트:
- libcamera가 설치되어 있고 `libcamera-vid`가 실행 가능한지 확인
- Raspberry Pi의 GPIO 핀 배선(BCM 번호)이 코드와 일치하는지 확인
- `yolov8n.pt` 모델 파일이 프로젝트 루트에 있는지 확인

---

## 알려진 문제 및 권장 개선
- `sensors/lintracer.py`의 `getLineValues()`는 현재 값을 반환하지 않습니다. `return value` 추가 필요.
- `sensors/__init__.py`의 `get_line_values` 와 실제 함수명 불일치(대소문자/언더스코어) — 하나로 통일 권장.
- 예외 처리: `yoloDetection.py`의 외부 프로세스(카메라) 실패 시 더 견고한 재시도 로직이 있으면 좋습니다.

---

필요하시면 제가 바로 `lintracer.py`의 `return` 추가나 `__init__.py`의 이름 정리 같은 소스 수정도 해드릴게요. 어떤 방식으로 통일할지(언더스코어 vs CamelCase) 알려주세요.

---

작성일: 2025-11-18


