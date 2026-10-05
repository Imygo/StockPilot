package com.stockpilot.stockpilot_api.service.indicator;

import com.stockpilot.stockpilot_api.dto.IndicatorSeriesResponse;
import com.stockpilot.stockpilot_api.dto.UpdateDailyChartResponse;
import com.stockpilot.stockpilot_api.global.enums.TechnicalIndicator;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;

// Java로 구현한다면 같은 디렉토리에 구현 클래스를 생성한다.
public interface TechnicalIndicatorCalculator {
    // 표시 시작일 이전에 추가로 필요한 캔들 개수
    int requiredHistoryBars(Set<TechnicalIndicator> indicators);

    // candles는 과거 데이터까지 포함하고 날짜 오름차순으로 전달
    // 결과는 displayStart~displayEnd에 해당하는 날짜만 반환
    List<IndicatorSeriesResponse> calculate(
            List<UpdateDailyChartResponse> candles,
            Set<TechnicalIndicator> indicators,
            LocalDate displayStart,
            LocalDate displayEnd
    );
}
