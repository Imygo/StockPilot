package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.DailyChartData;
import com.stockpilot.stockpilot_api.domain.DailyChartDataId;
import com.stockpilot.stockpilot_api.domain.MinuteChartData;
import com.stockpilot.stockpilot_api.domain.MinuteChartDataId;
import com.stockpilot.stockpilot_api.dto.*;
import com.stockpilot.stockpilot_api.repository.DailyChartDataRepository;
import com.stockpilot.stockpilot_api.repository.MinuteChartDataRepository;
import com.stockpilot.stockpilot_api.repository.StockRepository;
import lombok.RequiredArgsConstructor;
import org.hibernate.sql.Update;
import org.springframework.cglib.core.Local;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.NoSuchElementException;

@Service
@RequiredArgsConstructor
public class ChartService {
    private final DailyChartDataRepository dailyChartDataRepository;
    private final MinuteChartDataRepository minuteChartDataRepository;
    private final StockRepository stockRepository;

    // 컨트롤러 계층에서 차트를 구성할 수 있도록 데이터를 요청하고,
    // 관련된 데이터를 제공하도록 하는 메서드를 선언

    // 일봉 데이터를 얻어오기 위해선 거래 기간이 필요함
    // 시작기간과 종료기간을 담은 UpdateDailyChartRequest를 매개변수로 받아오고,
    // 해당기간 사이의 값을 sql로 조회한다.
    @Transactional(readOnly = true)
    public List<UpdateDailyChartResponse> getDailyChartData(
            String stockCode,
            UpdateDailyChartRequest request
    ){
        LocalDate start = request.getStartDate();
        LocalDate end = request.getEndDate();

        // 초기 상태가 둘 다 null일 경우 기본범위를 설정해야 한다.
        if(start == null || end == null){
            throw new IllegalArgumentException("시작일과 종료일을 선택해주세요. ");
        }
        if(start.isAfter(end)){
            throw new IllegalArgumentException("시작일은 종료일보다 늦을 수 없습니다.");
        }
        if(!stockRepository.existsById(stockCode)){
            throw new NoSuchElementException("존재하지 않는 종목입니다.");
        }

        return dailyChartDataRepository.findRange(stockCode, start, end)
                .stream()
                .map(this::toDailyResponse)
                .toList();
    }

    private UpdateDailyChartResponse toDailyResponse(DailyChartData data){
        return new UpdateDailyChartResponse(
                data.trade_date,
                data.close_price,
                data.open_price,
                data.high_price,
                data.low_price,
                data.volume
        );
    }

    // 분봉 차트를 구성하기 위한 데이터들을 전달하는 함수
    @Transactional(readOnly = true)
    public List<UpdateMinuteChartResponse> getMinuteChartData(
            String stockCode,
            UpdateMinuteChartRequest request
    ){
        LocalDateTime candleStart = request.getCandleStart();

        if(candleStart == null){
            // candleStart가 null일때의 처리가 없음, 생략 가능하므로 기본조회 시각을 설정한다.
            // 사용자가 분봉차트를 조회하는 시각을 기본 조회 시각으로 설정
            // 최근 60분을 보여주는 코드로 변경
            candleStart = LocalDateTime.now(ZoneId.of("Asia/Seoul"))
                    .minusMinutes(60)
                    .truncatedTo(java.time.temporal.ChronoUnit.MINUTES);
        }

        if(!stockRepository.existsById(stockCode)){
            throw new NoSuchElementException("존재하지 않는 종목입니다.");
        }

        return minuteChartDataRepository.findByDateAfter(stockCode, candleStart)
                .stream()
                .map(this::toMinuteResponse)
                .toList();
    }

    private UpdateMinuteChartResponse toMinuteResponse(MinuteChartData data){
        return new UpdateMinuteChartResponse(
                data.stock_code,
                data.candle_start,
                data.close_price,
                data.open_price,
                data.high_price,
                data.low_price
        );
    }

    // 지표연산을 위해 데이터를 얻어오는 함수
    public List<UpdateDailyChartResponse> getChartData(
            String stockCode,
            UpdateChartByIndicatorRequest request
    ){
        // 기간 검증
        LocalDate start = request.getStartDate();
        LocalDate end = request.getEndDate();

        if(start == null || end == null){
            throw new IllegalArgumentException("시작일과 종료일은 필수입니다.");
        }
        if(start.isAfter(end)){
            throw new IllegalArgumentException("시작일은 종료일보다 늦을 수 없습니다.");
        }

        // 종목 검증
        if(!stockRepository.existsById(stockCode)){
            throw new NoSuchElementException("존재하지 않는 종목입니다.");
        }

        // 선택 지표 확인

        // 계산에 필요한 과거 일봉까지 조회

        // 지표 계산

        // 표시 기간의 캔들과 지표 결과를 묶어서 반환

        return dailyChartDataRepository.findRange(stockCode, start, end)
                .stream()
                .map(this::toIndicatorResponse)
                .toList();
    }

    private UpdateDailyChartResponse toIndicatorResponse(DailyChartData data){
        return new UpdateDailyChartResponse(
                data.trade_date,
                data.close_price,
                data.open_price,
                data.high_price,
                data.low_price,
                data.volume
        );
    }



}
