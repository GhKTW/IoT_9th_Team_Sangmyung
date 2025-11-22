package com.example.iot_9th_team_sangmyung.domain.sensor.dto.request;

public record SensorRequestDTO(
        double distance,       // 거리
        double lightLevel,     // 조도
        String detectedObject, // 감지된 객체명 (예: "pallet", "drop_zone", "none")
        String status          // 현재 동작 상태
) {}
