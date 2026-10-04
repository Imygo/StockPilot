package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.DailyChartData;
import com.stockpilot.stockpilot_api.domain.DailyChartDataId;
import com.stockpilot.stockpilot_api.dto.UpdateChartByIndicatorResponse;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDate;
import java.util.List;

public interface DailyChartDataRepository extends JpaRepository<DailyChartData, DailyChartDataId> {
    @Query("""
    SELECT d
    FROM DailyChartData d
    WHERE d.stock_code = :stockCode
      AND d.trade_date BETWEEN :startDate AND :endDate
    ORDER BY d.trade_date ASC
    """)
    List<DailyChartData> findRange(
            @Param("stockCode") String stockCode,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate
    );
}
