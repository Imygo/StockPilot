package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.Stock;
import com.stockpilot.stockpilot_api.dto.StockListRequest;
import com.stockpilot.stockpilot_api.dto.StockSpecResponse;
import com.stockpilot.stockpilot_api.global.enums.Market;
import com.stockpilot.stockpilot_api.global.enums.StockSortType;
import com.stockpilot.stockpilot_api.repository.StockRepository;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.NoSuchElementException;

@Service
@RequiredArgsConstructor
public class StockService {
    private final StockRepository stockRepository;

    // 주식데이터를 요청할 경우 db에서 가져오도록 하는 것
    @Transactional(readOnly = true)
    public List<StockSpecResponse> searchStocks(String keyword){
        // 검색어 검증
        // Repository에서 코드 일치 또는 이름 포함 검색
        List<Stock> stocks;

        if(keyword == null){
            stocks = stockRepository.findAll(
                    Sort.by("volume").descending()
            );
        }else{
            String normalized = keyword.strip();

            if(normalized.isEmpty()){
                throw new IllegalArgumentException("검색어를 입력해주세요.");
            }

            stocks = stockRepository.searchByKeyword(normalized);
        }

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

    // 스톡 리스트를 구성하는 데이터는 제공하지만, 하나의 주식 상세를 제공하는 기능이 없어서 추가
    //  -> StockSpecResponse라는 DTO는 있지만 서비스 계층에 없었다는 것
    @Transactional(readOnly = true)
    public StockSpecResponse getStockSpec(String stockCode){
        if(stockCode == null || stockCode.isBlank()){
            throw new IllegalArgumentException("종목코드는 필수입니다.");
        }

        return stockRepository.findById(stockCode)
                .map(this::toResponse)
                .orElseThrow(() ->
                        new NoSuchElementException("존재하지 않는 주식코드입니다.")
                );
    }

    // 검색어가 생략됐는지, 공백인지 구분
    // 시장 조건을 적용. ALL은 시장 제한 없이 조회
    // 정렬 조건을 적용한다.
    // 조회한 Stock들을 기존 toResponse()로 변환

    @Transactional(readOnly = true)
    public List<StockSpecResponse> getStocks(StockListRequest request) {
        String keyword = request.getKeyword() == null
                ? null
                : request.getKeyword().strip();

        if(keyword != null && keyword.isEmpty()){
            throw new IllegalArgumentException("검색어를 입력해주세요.");
        }

        Market market = request.getMarket();

        if(market == Market.ALL){
            market = null;
        }

        StockSortType type = request.getSort() == null
                ? StockSortType.VOLUME_DESC
                :request.getSort();

        Sort sort = switch (type) {
            case VOLUME_DESC, SEARCH_PRIORITY ->
                    Sort.by(Sort.Direction.DESC, "volume");
            case PRICE_DESC ->
                    Sort.by(Sort.Direction.DESC, "current_price");
            case PRICE_ASC ->
                    Sort.by(Sort.Direction.ASC, "current_price");
            case CHANGE_RATE_DESC ->
                    Sort.by(Sort.Direction.DESC, "change_rate");
            case CHANGE_RATE_ASC ->
                    Sort.by(Sort.Direction.ASC, "change_rate");
            case MARKET_CAP_DESC ->
                    Sort.by(Sort.Direction.DESC, "marketCap");
            case NAME_ASC ->
                    Sort.by(Sort.Direction.ASC, "stock_name");
            case CODE_ASC ->
                    Sort.by(Sort.Direction.ASC, "stock_code");
        };

        return stockRepository.findStocks(
                        keyword,
                        market,
                        type == StockSortType.SEARCH_PRIORITY,
                        sort
                )
                .stream()
                .map(this::toResponse)
                .toList();

    }
}
