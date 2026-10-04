package com.stockpilot.stockpilot_api.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;
import java.util.List;

// 기술적지표는 사용자가 정한 기간만큼의 데이터를 들고오기 때문에 daily_chart_data db를 이용합니다.
// 또한 데이터를 재구성하기 위해 필요한 값은 시가, 종가, 고가, 저가이며 사용자가 지정한 기간이 맞는지 확인하기 위해 tradeDate가 필요함.
// 과거의 데이터를 기반으로 구성하기 때문에 실시간 데이터가 필요하다면 LocalDateTime을 추가할 필요가 있음
// 사용자가 시작기간을 설정하고 종료기간을 설정하지 않는다면 실시간 데이터를, 그렇지 않다면 현재 설계대로 하면 될 것 같음

//  RSI, MA, BB를 구현할 때 정해야 하는 것
// 프론트엔드 계산 : 백엔드가 계산에 필요한 과거 캔들까지 제공
// 백엔드 계산 : 응답에 캔들 목록과 지표별 계산 결과를 함꼐 제공

@Getter
@AllArgsConstructor
public class UpdateChartByIndicatorResponse {
    private String stockCode;
    private List<UpdateDailyChartResponse> candles;
    private List<IndicatorSeriesResponse> indicatorSeriesResponses;
}
