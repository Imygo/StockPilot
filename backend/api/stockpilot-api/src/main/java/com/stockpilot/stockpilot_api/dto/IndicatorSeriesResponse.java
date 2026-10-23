package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.TechnicalIndicator;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.List;

@Getter
@AllArgsConstructor
public class IndicatorSeriesResponse {
    private TechnicalIndicator indicator;
    private String line;
    private List<IndicatorPointResponse> points;
}
