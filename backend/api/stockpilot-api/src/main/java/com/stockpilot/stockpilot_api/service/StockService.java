package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.Stock;
import com.stockpilot.stockpilot_api.dto.StockSpecResponse;
import com.stockpilot.stockpilot_api.repository.StockRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class StockService {
    private final StockRepository stockRepository;

    // 주식데이터를 요청할 경우 db에서 가져오도록 하는 것
    @Transactional(readOnly = true)
    public List<StockSpecResponse> searchStocks(String keyword){
        // 검색어 검증
        // Repository에서 코드 일치 또는 이름 포함 검색
        List<Stock> stocks = stockRepository.searchByKeyword(keyword);

        return stocks.stream()
                .map(this::toResponse)
                .toList();
    }

    private StockSpecResponse toResponse(Stock stock) {
        return new StockSpecResponse(
                stock.stock_code,
                stock.stock_name,
                stock.market,
                stock.current_price,
                stock.marketCap,
                stock.change_rate,
                stock.change_amount,
                stock.volume,
                stock.updated_at
        );
    }
}
