package com.stockpilot.stockpilot_api.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class UserOpinionRequest {
    // 시스템은 사용자가 매수 추천, 중립, 매도 추천 중 하나의 의견을 입력할 수 있도록 해야 한다.
    // global/enum/OpinionType의 BUY, NEUTRAL, SELL 의 값을 버튼을 통해 전달하는 것.
    @NotNull(message = "의견을 선택해야 합니다.")
    private OpinionType opinion;
}
