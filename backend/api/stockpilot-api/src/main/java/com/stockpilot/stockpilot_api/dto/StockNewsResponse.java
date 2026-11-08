package com.stockpilot.stockpilot_api.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.OffsetDateTime;

@Getter
@AllArgsConstructor
public class StockNewsResponse {
    String articleId;
    String stockCode;
    String stockName;
    String title;
    String description;
    String url;
    OffsetDateTime publishedAt;
    String label;
    double negative;
    double neutral;
    double positive;
    String modelVersion;
    String qualityJson;
}
