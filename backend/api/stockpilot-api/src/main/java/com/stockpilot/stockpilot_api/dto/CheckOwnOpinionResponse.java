package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@AllArgsConstructor
public class CheckOwnOpinionResponse {
    private OpinionType opinion;
    private LocalDateTime updated_at;
}
