package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.TechnicalIndicator;

import java.util.List;

public class IndicatorSeriesResponse {
    private TechnicalIndicator indicator;
    private String line;
    private List<IndicatorPointResponse> points;
}
