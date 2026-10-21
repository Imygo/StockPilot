package com.stockpilot.stockpilot_api.controller;

// GET /api/stocks/{stockCode}/ai-opinion

import com.stockpilot.stockpilot_api.domain.AiOpinions;
import com.stockpilot.stockpilot_api.dto.AiOpinionResponse;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import com.stockpilot.stockpilot_api.service.AiOpinionService;
import lombok.NoArgsConstructor;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/stocks")
@RequiredArgsConstructor
public class AiOpinionController {

    private final AiOpinionService aiOpinionService;

    // 특정 주식의 AI의견을 받아오도록 Service에게 요청
    // GET /api/stocks/{stockCode}/ai-opinion
    @GetMapping("/{stockCode}/ai-opinion")
    public AiOpinionResponse getAiOpinion(
            @PathVariable("stockCode") String stockCode){
        return aiOpinionService.getAiOpinion(stockCode);
    }
}
