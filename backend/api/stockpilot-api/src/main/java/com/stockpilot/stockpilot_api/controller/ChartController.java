package com.stockpilot.stockpilot_api.controller;

// GET /api/stocks/{stockCode}/chart
// GET /api/stocks/{stockCode}/chart

import com.stockpilot.stockpilot_api.domain.Stock;
import com.stockpilot.stockpilot_api.dto.*;
import com.stockpilot.stockpilot_api.service.ChartService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/stocks")
@RequiredArgsConstructor
public class ChartController {
    private final ChartService chartService;

    // 일봉차트 데이터 요청
    @GetMapping("/{stockCode}/daily-chart")
    public List<UpdateDailyChartResponse> getDailyChartData(
            @PathVariable("stockCode") String stockCode,
            @Valid @ModelAttribute UpdateDailyChartRequest request
    ){
        // UpdateDailyChartRequest를 위해 startDate, endDate값을 받아야 하지만, 어떻게 전달받아야 할 지 결정
        // 일단 api요청경로를 통해 받는다면 경로를 재설정

        return chartService.getDailyChartData(stockCode, request);
    }

    @GetMapping("/{stockCode}/minute-chart")
    public List<UpdateMinuteChartResponse> getMinuteChartData(
            @PathVariable("stockCode") String stockCode,
            @Valid @ModelAttribute UpdateMinuteChartRequest request
    ){
        // candleStart는 사용자가 minute-chart를 요청한 시점을 기준으로 하기 때문에, 그 값을 지정하기만 하면됨.
        // 이건 Service 계층에서 값을 지정하기 때문에, null로 초기화 한다.
        return chartService.getMinuteChartData(stockCode, request);
    }

    @GetMapping("/{stockCode}/indicator-chart")
    public List<UpdateDailyChartResponse> getIndicatorChartData(
            @PathVariable("stockCode") String stockCode,
            @Valid @ModelAttribute UpdateChartByIndicatorRequest request
    ){
        // getDailyChartData와 결이 같다.
        return chartService.getChartData(stockCode, request);
    }
}
