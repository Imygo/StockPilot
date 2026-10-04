package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.TechnicalIndicator;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDate;
import java.util.List;

@Getter
@Setter
@NoArgsConstructor
public class UpdateDailyChartRequest {
    // 요청할 때 필요한 값은 다음과 같다.
    // stockCode는 URL경로에서 받으므로 DTO에 넣을 필요 없음e
    private String stockCode;
    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
    private LocalDate startDate;
    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
    private LocalDate endDate;
}
