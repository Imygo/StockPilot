package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.Market;
import com.stockpilot.stockpilot_api.global.enums.StockSortType;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor

// api문서에서 합의한 URL : GET /api/stocks?keyword=삼성&sort=PRICE_DESC&market=KOSPI
// Keyword, Market, Sort요청을 StockListRequest 하나로 해결함

// keyword 생략 >> 기본 목록 조회
// keyword가 빈 문자열 또는 공백 >> 400 bad request 또는 실패처리
// 유효한 검색어 >> 검색 수행

public class StockListRequest {
    private String keyword;
    private StockSortType sort;
    private Market market;
}
