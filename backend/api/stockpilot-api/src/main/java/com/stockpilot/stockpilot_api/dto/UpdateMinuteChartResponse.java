package com.stockpilot.stockpilot_api.dto;

import lombok.Getter;

import java.time.LocalDateTime;

@Getter
public class UpdateMinuteChartResponse {
    private String stockCode;
    private LocalDateTime candleStart;
    private Integer closePrice;
    private Integer openPrice;
    private Integer highPrice;
    private Integer lowPrice;

    public UpdateMinuteChartResponse(String stockCode, LocalDateTime candleStart, Integer closePrice, Integer openPrice, Integer highPrice, Integer lowPrice) {
        this.stockCode = stockCode;
        this.candleStart = candleStart;
        this.closePrice = closePrice;
        this.openPrice = openPrice;
        this.highPrice = highPrice;
        this.lowPrice = lowPrice;
    }
}
