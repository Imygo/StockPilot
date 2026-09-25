package com.stockpilot.stockpilot_api.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
// keyword 생략 >> 기본 목록 조회
// keyword가 빈 문자열 또는 공백 >> 400 bad request 또는 실패처리
// 유효한 검색어 >> 검색 수행

// 생략은 허용하고, 전달했다면 공백이면 안된다.
public class StockSearchByKeywordRequest {
    // 시스템은 사용자가 종목명 또는 종목코드를 입력할 수 있도록 해야 한다.
    private String keyword;

    
}
