package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.MinuteChartData;
import com.stockpilot.stockpilot_api.domain.MinuteChartDataId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface MinuteChartDataRepository extends JpaRepository<MinuteChartData, MinuteChartDataId> {
}
