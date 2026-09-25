package com.stockpilot.stockpilot_api.dto;

import lombok.Getter;

@Getter
public class AiOpinionResponse {
    private String aiOpinion;

    public AiOpinionResponse(String aiOpinion) {
        this.aiOpinion = aiOpinion;
    }
}
