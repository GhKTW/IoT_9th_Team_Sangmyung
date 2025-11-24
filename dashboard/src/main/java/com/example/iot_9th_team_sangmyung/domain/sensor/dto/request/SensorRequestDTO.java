package com.example.iot_9th_team_sangmyung.domain.sensor.dto.request;

public record SensorRequestDTO(
        double distance,       // 전방 거리
        double lightLevel,     // 조도 센서 값
        double weight,         // 현재 무게
        boolean isOverloaded,  //  과적 여부 (True면 경고)
        boolean isLightOn,     //  라이트 켜짐 여부
        String detectedObject, // 감지된 객체 (YOLO)
        String status          // 현재 로봇 상태 (MOVING, LIFTING, WARNING 등)
) {}
