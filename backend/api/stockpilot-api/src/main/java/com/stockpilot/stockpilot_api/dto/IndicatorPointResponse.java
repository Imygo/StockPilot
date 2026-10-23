package com.stockpilot.stockpilot_api.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.LocalDate;

@Getter
@AllArgsConstructor
public class IndicatorPointResponse {
    private LocalDate tradeDate;
    private Double value;
}
