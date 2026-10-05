package com.stockpilot.stockpilot_api.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import com.stockpilot.stockpilot_api.global.enums.TechnicalIndicator;
import org.springframework.format.annotation.DateTimeFormat;

import java.time.LocalDate;
import java.util.List;

@Getter
@Setter
@NoArgsConstructor
public class UpdateChartByIndicatorRequest {
    // 요청할 때 필요한 값은 다음과 같다.
    // 시작일자, 종료일자, 적용할 지표
    // stockCode는 URL경로에서 받으므로 DTO에 넣을 필요 없음
    private List<TechnicalIndicator> technicalIndicators;

    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
    private LocalDate startDate;

    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
    private LocalDate endDate;

    // 합의해야하는 것들
    // 기간을 생략한 기본 차트 조회에서 사용할 기간
    // startDate가 endDate보다 늦은 경우의 처리
    // 일봉과 분봉 중 어떤 데이터를 요청하는지 구분하는 방법
    // 기술적 지표를 백엔드와 프론트엔드 중 어디서 계산할지

}
