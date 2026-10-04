package com.stockpilot.stockpilot_api.dto;

import lombok.Getter;

import java.time.LocalDate;

@Getter
public class UpdateDailyChartResponse {
    private LocalDate tradeDate;
    private Integer closePrice;
    private Integer openPrice;
    private Integer highPrice;
    private Integer lowPrice;
    private Long volume;

    public UpdateDailyChartResponse(LocalDate tradeDate, Integer closePrice, Integer openPrice, Integer highPrice, Integer lowPrice, Long volume) {
        this.tradeDate = tradeDate;
        this.closePrice = closePrice;
        this.openPrice = openPrice;
        this.highPrice = highPrice;
        this.lowPrice = lowPrice;
        this.volume = volume;
    }
}
