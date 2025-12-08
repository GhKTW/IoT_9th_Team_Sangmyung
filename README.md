# 스마트 지게차 (Autonomous Forklift)

YOLOv8 기반 객체 인식과 센서 융합을 통한 자율주행 스마트 지게차 시스템

## 목차
- [프로젝트 개요](#프로젝트-개요)
- [주요 기능](#주요-기능)
- [시스템 구성](#시스템-구성)
- [설치 방법](#설치-방법)
- [사용 방법](#사용-방법)
- [코드 구조](#코드-구조)
- [하드웨어 요구사항](#하드웨어-요구사항)

## 프로젝트 개요

이 프로젝트는 YOLOv8 객체 인식 모델과 다양한 센서(거리센서, 로드셀, 조도센서, 라인트레이서)를 활용하여 자율적으로 물체를 찾아 운반하는 지게차 시스템입니다.

### 작동 프로세스
1. **객체 탐지**: 카메라로 목표 물체(사과, 바나나, 브로콜리) 탐지
2. **경로 추적**: 탐지된 물체를 향해 자율 주행
3. **물체 적재**: 거리센서로 물체 위치 확인 후 들어올리기
4. **운반**: 목적지(트럭)까지 물체 운반
5. **하차**: 트럭에 물체 내려놓기

## 주요 기능

### 1. 객체 인식 및 추적
- YOLOv8n 모델을 사용한 실시간 객체 탐지
- 타겟 물체: 사과(apple), 바나나(banana), 브로콜리(broccoli), 트럭(truck)
- 카메라 프레임 버퍼링을 통한 안정적인 영상 처리

### 2. 자율 주행
- 중앙 정렬 알고리즘으로 물체를 향한 정확한 주행
- Dead Zone(±28px)을 이용한 미세 조정
- 라인트레이서를 통한 목적지 도착 감지

### 3. 물체 적재 시스템
- 거리센서 3개를 이용한 물체 감지
- 로드셀 2개를 통한 무게 측정
- 과부하 방지 시스템 (최대 55,000 단위, 경고 80%)

### 4. 조명 자동 제어
- 조도센서를 통한 주변 밝기 감지
- 어두울 때(≤10) 자동 조명 점등
- 5초 주기로 모니터링

### 5. 실시간 서버 통신
- 현재 상태, 무게, 과부하 여부를 서버로 전송
- 상태 종류: SEARCHING, LIFTING, TRANSPORTING, UNLOADING, OVERLOAD, ARRIVED

## 시스템 구성

### 소프트웨어 스택
```
Python 3.x
├── OpenCV (cv2): 영상 처리
├── Ultralytics (YOLO): 객체 인식
├── NumPy: 수치 연산
├── Requests: HTTP 통신
└── Threading: 비동기 처리
```

### 센서 구성
- **카메라**: libcamera-vid (640x640, 30fps)
- **거리센서**: 3개 (전면 좌/중/우)
- **로드셀**: 2개 (무게 측정)
- **조도센서**: 1개 (밝기 감지)
- **라인트레이서**: 3개 센서 (경로 감지)

## 설치 방법

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/autonomous-forklift.git
cd autonomous-forklift
```

### 2. 의존성 설치
```bash
pip install opencv-python
pip install ultralytics
pip install numpy
pip install requests
```

### 3. YOLO 모델 다운로드
```bash
# YOLOv8n 모델이 자동으로 다운로드됩니다
# 또는 수동으로 다운로드:
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
```

### 4. 센서 모듈 설정
```python
# sensors.py 파일이 필요합니다
# SPI 통신 설정 및 센서 초기화 함수 포함
```

## 사용 방법

### 기본 실행
```bash
python main.py
```

### 서버 URL 설정
코드 내 `SERVER_URL` 변수를 수정하세요:
```python
SERVER_URL = "http://your-server-ip:8080/api/sensor/data"
```

### 타겟 물체 변경
```python
target_order = [47, 46, 50]  # apple, banana, broccoli
# YOLO 클래스 ID를 원하는 순서로 배열
```

### 프로그램 종료
```
Ctrl + C (KeyboardInterrupt)
```

## 코드 구조

```
autonomous-forklift/
├── main.py                 # 메인 프로그램
├── sensors.py              # 센서 제어 모듈
├── yolov8n.pt              # YOLO 모델 파일
└── README.md               # 프로젝트 문서
```

### 주요 함수

#### 통신 관련
- `get_sensor_state()`: 현재 센서 상태 정보 반환
- `send_data()`: 서버로 데이터 전송

#### 모터 제어
- `move_forward()`, `move_backward()`: 전진/후진
- `turn_left()`, `turn_right()`: 좌회전/우회전
- `stop()`: 정지

#### 객체 인식
- `detect_object()`: YOLO를 이용한 객체 탐지
- `read_frames()`: 카메라 프레임 읽기 (쓰레드)

#### 물체 적재
- `attempt_lift()`: 물체 들어올리기 시도
- `attempt_place()`: 물체 내려놓기
- `lift_down_weight()`: 리프트 내리기

#### 자율 주행
- `track_step()`: 타겟 추적 및 이동 제어

#### 조명 제어
- `light_sensor_monitor()`: 조도센서 모니터링 (쓰레드)

## 하드웨어 요구사항

### 필수 하드웨어
- Raspberry Pi 4 이상 (카메라 모듈 지원)
- Raspberry Pi Camera Module
- DC 모터 4개 + 모터 드라이버
- 리프트용 모터 1개
- 거리센서 3개 (초음파 또는 적외선)
- 로드셀 2개 + HX711 앰프
- 조도센서 1개
- 라인트레이서 센서 3개
- LED 조명

### 전원
- 12V 배터리 (모터 구동용)
- 5V 레귤레이터 (Raspberry Pi용)

## 설정값 조정

### 무게 임계값
```python
MAX_LIFT_STOP_RAW_VALUE = 55000  # 최대 적재 무게
OVERLOAD_WARNING_THRESHOLD = MAX_LIFT_STOP_RAW_VALUE * 0.8  # 과부하 경고
```

### 트래킹 파라미터
```python
DEAD_ZONE = 28  # 중앙 허용 오차 (픽셀)
FRAME_WIDTH_DEFAULT = 640  # 프레임 너비
```

### 조명 제어
```python
light_value <= 10  # 조명 켜는 밝기 임계값
time.sleep(5)  # 조도센서 체크 주기 (초)
```

## 동작 상태

시스템은 다음 상태들을 순환합니다:

1. **SEARCHING**: 물체 탐색 중
2. **LIFTING**: 물체 들어올리기 중
3. **TRANSPORTING**: 물체 운반 중
4. **UNLOADING**: 물체 내려놓기 중
5. **OVERLOAD**: 과부하 감지
6. **ARRIVED**: 작업 완료