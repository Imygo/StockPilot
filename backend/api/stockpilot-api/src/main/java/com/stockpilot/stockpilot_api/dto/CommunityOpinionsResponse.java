package com.stockpilot.stockpilot_api.dto;

import lombok.Getter;

// 사용자가 주식 상세정보를 확인하려고 했을 때, 커뮤니티의 의견을 보여야 하므로 DB에서 응답을 받기만 함
@Getter
public class CommunityOpinionsResponse {
    private String stockCode;
    private Integer buy;
    private Integer neutral;
    private Integer sell;

    public CommunityOpinionsResponse(String stockCode, Integer buy, Integer neutral, Integer sell) {
        this.stockCode = stockCode;
        this.buy = buy;
        this.neutral = neutral;
        this.sell = sell;
    }
}
