package com.stockpilot.stockpilot_api.controller;

import com.stockpilot.stockpilot_api.dto.StockListRequest;
import com.stockpilot.stockpilot_api.dto.StockSpecResponse;
import com.stockpilot.stockpilot_api.service.StockService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.Value;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/stocks")
@RequiredArgsConstructor
public class StockController {

    private final StockService stockService;

    // 주식 리스트를 구성하는 데이터를 받아오도록 StockService에게 명령
    // GET /api/stocks
    // GET /api/stocks?keyword=삼성
    // GET /api/stocks?market=KOSPI
    // GET /api/stocks?keyword=삼성&market=KOSPI&sort=VOLUME_DESC
    @GetMapping
    public List<StockSpecResponse> getStocks(
            @Valid @ModelAttribute StockListRequest request
            ) {
        // 검색어를 이용하여 주식코드 일치 또는 이름 포함 검색
        return stockService.getStocks(request);
    }

    // 주식 상세 정보를 받아오도록 명령
    // GET /api/stocks/{stockCode}
    // URL의 파라미터를 stockCode로 전달
    @GetMapping("/{stockCode}")
    public StockSpecResponse getStockDetail(
            @PathVariable("stockCode") String stockCode
    ) {
        return stockService.getStockSpec(stockCode);
    }
}
