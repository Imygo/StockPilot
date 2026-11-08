package com.stockpilot.stockpilot_api.controller;

import com.stockpilot.stockpilot_api.dto.StockNewsResponse;
import com.stockpilot.stockpilot_api.repository.StockNewsRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@RestController
@RequiredArgsConstructor
public class StockNewsController {
    private final StockNewsRepository stockNewsRepository;

    @GetMapping("/api/stocks/{stockCode}/news")
    public List<StockNewsResponse> news(
            @PathVariable("stockCode") String stockCode,
            @RequestParam(name = "limit", defaultValue = "30") int limit,
            @RequestParam(name = "modelVersion", required = false)
            String modelVersion
    ) {
        if (!stockCode.matches("[0-9A-Z]{6}")
                || limit < 1 || limit > 100
                || (modelVersion != null
                && !modelVersion.matches("[0-9a-f]{64}"))) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Invalid stockCode, limit or modelVersion"
            );
        }

        String version = modelVersion;
        if (version == null) {
            version = stockNewsRepository
                    .findLatestModelVersion(stockCode)
                    .orElse(null);
        }

        if (version == null) {
            return List.of();
        }

        return stockNewsRepository.findNews(stockCode, version, limit);
    }
}