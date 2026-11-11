package com.stockpilot.stockpilot_api.controller;

// GET /api/stocks/{stockCode}/community-opinion
// POST /api/stocks/{stockCode}/user-opinion
// GET /api/stocks/{stockCode}/own-opinion

import com.stockpilot.stockpilot_api.dto.CheckOwnOpinionResponse;
import com.stockpilot.stockpilot_api.dto.CommunityOpinionViewResponse;
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

    // 본인이 제출한 의견을 받아오는 함수
    // GET /api/stocks/{stockCode}/own-opinion
    @GetMapping("/own-opinion")
    public CheckOwnOpinionResponse getOwnOpinion(
            @PathVariable("stockCode") String stockCode,
            @SessionAttribute(
                    name = "userId",
                    required = false
            ) String userId
    ){
        if(userId == null){
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED,
                    "사용자 식별 세션이 필요합니다."
            );
        }
        return opinionService.getOwnOpinion(userId, stockCode);
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
