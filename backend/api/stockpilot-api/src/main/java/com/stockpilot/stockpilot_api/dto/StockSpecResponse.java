package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.Market;
import lombok.Getter;

import java.time.LocalDateTime;

// 시스템은 종목명, 종목코드, 시장 구분, 현재가, 등락값 및 등락률, 거래량, 시가총액을 표시해야 한다.
// 사용자가 DB에 입력하지 않고, 기록된 값을 그대로 불러오기만 하면 되므로.
@Getter
public class StockSpecResponse {
    private String stockCode;
    private String stockName;
    private Market market;
    private Integer currentPrice;
    private Long marketCap;
    private Double changeRate;
    private Double changeAmount;
    private Long volume;
    private LocalDateTime updatedAt;

    public StockSpecResponse(String stockCode, String stockName, Market market, Integer currentPrice, Long marketCap, Double changeRate, Double changeAmount, Long volume, LocalDateTime updatedAt) {
        this.stockCode = stockCode;
        this.stockName = stockName;
        this.market = market;
        this.currentPrice = currentPrice;
        this.marketCap = marketCap;
        this.changeRate = changeRate;
        this.changeAmount = changeAmount;
        this.volume = volume;
        this.updatedAt = updatedAt;
    }
}
