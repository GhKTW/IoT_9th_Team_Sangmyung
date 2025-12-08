package com.example.iot_9th_team_sangmyung.domain.sensor.controller;

import com.example.iot_9th_team_sangmyung.domain.sensor.dto.request.SensorRequestDTO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.*;

@Tag(name = "Sensor API", description = "IoT 센서 데이터 관리")
@RestController
@RequestMapping("/api/sensor")
public class SensorController {


    // DTO 변경에 맞춰 필드 순서와 개수를 수정해야 합니다. (weight, isOverloaded, isLightOn, detectedObject, status)
    private SensorRequestDTO latestData = new SensorRequestDTO(
            0.0,   // weight (무게 백분율 초기값)
            false, // isOverloaded (과적 여부)
            false, // isLightOn (조명 켜짐 여부)
            "NONE", // detectedObject (객체명)
            "STANDBY" // status (로봇 상태)
    );

    @Operation(summary = "센서 데이터 수신 (From Pi)", description = "라즈베리파이에서 보낸 데이터를 받아서 갱신합니다.")
    @PostMapping("/data")
    public String receiveSensorData(@RequestBody SensorRequestDTO requestDTO) {
        this.latestData = requestDTO;
        System.out.println("UPDATE: " + requestDTO.status() + " / Object: " + requestDTO.detectedObject());
        return "OK";
    }

    @Operation(summary = "최신 데이터 조회 (For Frontend)", description = "프론트엔드 대시보드용 최신 데이터를 반환합니다.")
    @GetMapping("/current")
    public SensorRequestDTO getCurrentStatus() {
        return this.latestData;
    }
}