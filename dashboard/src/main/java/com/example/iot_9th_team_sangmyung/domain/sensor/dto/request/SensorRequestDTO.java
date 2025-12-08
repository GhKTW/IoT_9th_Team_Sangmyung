package com.example.iot_9th_team_sangmyung.domain.sensor.dto.request;

public record SensorRequestDTO(
        double weight,         // 현재 무게 (백분율: 0.0 ~ 100.0)
        boolean isOverloaded,  // 과적 여부 (True면 80% 이상 경고)
        boolean isLightOn,     // 라이트 켜짐 여부 (자동 제어 로직 결과)
        String detectedObject, // 감지된 객체 (apple, banana 등)
        String status          // 현재 로봇 상태 (LIFTING, UNLOADING, SEARCHING 등)
) {}
