package com.stockpilot.stockpilot_api.controller;

// GET /api/stocks/{stockCode}/community-opinion
// POST /api/stocks/{stockCode}/user-opinion

import com.stockpilot.stockpilot_api.dto.CommunityOpinionViewResponse;
import com.stockpilot.stockpilot_api.dto.CommunityOpinionsResponse;
import com.stockpilot.stockpilot_api.dto.UserOpinionRequest;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import com.stockpilot.stockpilot_api.service.OpinionService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/stocks/{stockCode}")
@RequiredArgsConstructor
public class OpinionController {
    private final OpinionService opinionService;

    @GetMapping("/community-opinion")
    public CommunityOpinionViewResponse getCommunityOpinions(
            @PathVariable("stockCode") String stockCode,
            @SessionAttribute(
                    name = "userId",
                    required = false
            ) String userId
    ) {
        return opinionService.getCommunityView(stockCode, userId);
    }

    @PostMapping("/user-opinion")
    public CommunityOpinionViewResponse postUserOpinion(
            @PathVariable("stockCode") String stockCode,
            @SessionAttribute(
                    name = "userId",
                    required = false
            ) String userId,
            @Valid @RequestBody UserOpinionRequest request
    ) {
        if (userId == null) {
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED,
                    "사용자 식별 세션이 필요합니다."
            );
        }

        return opinionService.saveAndGetView(userId, stockCode, request);
    }
}
