package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.MinuteChartData;
import com.stockpilot.stockpilot_api.domain.MinuteChartDataId;
import com.stockpilot.stockpilot_api.dto.UpdateChartByIndicatorResponse;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface MinuteChartDataRepository extends JpaRepository<MinuteChartData, MinuteChartDataId> {
    @Query("""
    SELECT m
    FROM MinuteChartData m
    WHERE m.stock_code = :stockCode
      AND m.candle_start >= :candleStart
    ORDER BY m.candle_start ASC
    """)
    List<MinuteChartData> findByDateAfter(
            @Param("stockCode") String stockCode,
            @Param("candleStart") LocalDateTime candleStart
    );
}
