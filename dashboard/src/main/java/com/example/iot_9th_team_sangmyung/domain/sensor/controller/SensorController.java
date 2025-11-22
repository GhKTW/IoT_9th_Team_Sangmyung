package com.example.iot_9th_team_sangmyung.domain.sensor.controller;

import com.example.iot_9th_team_sangmyung.domain.sensor.dto.request.SensorRequestDTO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Sensor API", description = "IoT 센서 데이터 관리")
@RestController
@RequestMapping("/api/sensor")
public class SensorController {

    // 최신 상태를 저장할 메모리 공간 (DB 대신 사용)
    private SensorRequestDTO latestData = new SensorRequestDTO(0, 0, "NONE", "WAITING");

    @Operation(summary = "센서 데이터 수신 (From Pi)", description = "라즈베리파이에서 보낸 데이터를 받아서 갱신합니다.")
    @PostMapping("/data")
    public String receiveSensorData(@RequestBody SensorRequestDTO requestDTO) {
        this.latestData = requestDTO; // 최신 데이터로 덮어쓰기
        System.out.println("UPDATE: " + requestDTO.status() + " / Light: " + requestDTO.lightLevel());
        return "OK";
    }

    @Operation(summary = "최신 데이터 조회 (For Frontend)", description = "프론트엔드 대시보드용 최신 데이터를 반환합니다.")
    @GetMapping("/current")
    public SensorRequestDTO getCurrentStatus() {
        return this.latestData;
    }
}