// IoT_9th_Team_Sangmyung/frontend/src/mock/deviceMock.ts

// API 응답 데이터 구조 정의
export interface SensorData {
  distance: number;       // 초음파 센서 거리 (cm)
  lightLevel: number;     // 조도 센서 값
  weight: number;         // 로드셀 무게 값 (백분율: 0.0 ~ 100.0)
  isOverloaded: boolean;  // 과부하 상태 (80% 이상)
  isLightOn: boolean;     // 라이트 켜짐 상태
  detectedObject: string; // 감지된 객체명
  status: string;         // 지게차 동작 상태 (SEARCHING, APPROACHING, LIFTING, TRANSPORTING, UNLOADING, OVERLOAD 등)
}

// 최대 적재량을 100%로 설정
const MAX_LOAD_PERCENTAGE = 100;
const OVERLOAD_THRESHOLD_PERCENTAGE = 80; // 80%를 과부하 경고 기준으로 사용

let currentWeight = 0;
let isLifting = false;

// Mock 데이터를 생성하는 함수
export const generateSensorData = (currentStatus: string): SensorData => {
  // 무게 변화 로직: LIFTING/UNLOADING/OVERLOAD 상태일 때만 변화
  if (currentStatus === 'LIFTING') {
    // 무게가 서서히 증가 (최대 105%까지 오를 수 있도록)
    currentWeight = Math.min(MAX_LOAD_PERCENTAGE * 1.05, currentWeight + Math.random() * 5);
    isLifting = true;
  } else if (currentStatus === 'UNLOADING' || currentStatus === 'OVERLOAD_RECOVERY') {
    // 무게가 서서히 감소
    currentWeight = Math.max(0, currentWeight - Math.random() * 5);
  } else if (currentStatus === 'TRANSPORTING' || currentStatus === 'WEIGHING') {
    // 운반 중이거나 측정 중에는 무게 유지
    currentWeight = Math.min(MAX_LOAD_PERCENTAGE, currentWeight);
    isLifting = currentWeight > 0;
  } else {
    // ARRIVED, STANDBY, SEARCHING 상태에서는 무게 0으로 리셋
    currentWeight = 0;
    isLifting = false;
  }

  // 무게를 0% ~ 100% 범위로 정규화 (전송 값)
  const normalizedWeight = Math.min(MAX_LOAD_PERCENTAGE, Math.max(0, currentWeight));

  const isOverloaded = normalizedWeight > OVERLOAD_THRESHOLD_PERCENTAGE; // 80% 초과 시 경고

  // 모터 및 라인 센서 값은 임의로 생성
  const distance = currentStatus === 'APPROACHING' ? Math.max(5, Math.floor(Math.random() * 20)) : 100;
  const lightLevel = Math.floor(Math.random() * 1000);
  const isLightOn = lightLevel < 100;

  // 감지된 객체는 상태에 따라 임의로 지정
  let detectedObject = "none";
  if (currentStatus === 'APPROACHING' || currentStatus === 'LIFTING' || currentStatus === 'TRANSPORTING' || currentStatus === 'WEIGHING') {
    detectedObject = ["apple", "banana", "broccoli"][Math.floor(Math.random() * 3)];
  }

  return {
    distance: parseFloat(distance.toFixed(1)),
    lightLevel: lightLevel,
    weight: parseFloat(normalizedWeight.toFixed(1)), // 백분율로 전송
    isOverloaded: isOverloaded,
    isLightOn: isLightOn,
    detectedObject: detectedObject,
    status: currentStatus,
  };
};

// 시뮬레이션 상태 업데이트용 (외부에서 무게를 설정하고 싶을 때 사용)
export const updateWeightForScenario = (newWeight: number) => {
  currentWeight = newWeight;
  isLifting = newWeight > 0;
};