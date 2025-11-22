package com.example.iot_9th_team_sangmyung.domain.sensor.dto.request;

public class SensorRequestDTO {
    public record SensorReqDTO(
            double distance,      // 초음파 거리
            double lightLevel,    // 조도 센서 값
            String detectedObject,// YOLO로 찾은 물체 이름 (예: "pallet")
            String status         // 현재 상태 (예: "SEARCHING", "LIFTING", "MOVING", "UNLOADING")
    ) {}
}
