package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import lombok.Getter;
import lombok.Setter;

@Getter
public class CommunityOpinionViewResponse {
    private String stockCode;
    private int buy;
    private int neutral;
    private int sell;
    private long totalCount;
    private boolean voted;
    private OpinionType myOpinion;

    public CommunityOpinionViewResponse(String stockCode, int buy, int neutral, int sell, long totalCount, boolean voted, OpinionType myOpinion) {
        this.stockCode = stockCode;
        this.buy = buy;
        this.neutral = neutral;
        this.sell = sell;
        this.totalCount = totalCount;
        this.voted = voted;
        this.myOpinion = myOpinion;
    }
}
