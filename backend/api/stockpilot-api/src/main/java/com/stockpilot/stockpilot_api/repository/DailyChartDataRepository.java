package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.DailyChartData;
import com.stockpilot.stockpilot_api.domain.DailyChartDataId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DailyChartDataRepository extends JpaRepository<DailyChartData, DailyChartDataId> {
}
