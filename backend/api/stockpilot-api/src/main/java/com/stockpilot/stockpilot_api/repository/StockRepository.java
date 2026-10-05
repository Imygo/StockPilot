package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.Stock;
import com.stockpilot.stockpilot_api.global.enums.Market;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface StockRepository extends JpaRepository<Stock, String> {
    @Query("""
        SELECT s
        FROM Stock s
        WHERE s.stock_code = :keyword
           OR s.stock_name LIKE CONCAT('%', :keyword, '%')
        """)
    // 키워드로 주식들을 반환하는 함수
    List<Stock> searchByKeyword(@Param("keyword") String keyword);

    @Query("""
    SELECT s
    FROM Stock s
    WHERE (
        :keyword IS NULL
        OR s.stock_code = :keyword
        OR s.stock_name LIKE CONCAT('%', :keyword, '%')
    )
    AND (:market IS NULL OR s.market = :market)
    ORDER BY CASE
        WHEN :searchPriority = true AND s.stock_code = :keyword THEN 0
        WHEN :searchPriority = true AND s.stock_name = :keyword THEN 1
        ELSE 2
    END
    """)
    List<Stock> findStocks(
            @Param("keyword") String keyword,
            @Param("market") Market market,
            @Param("searchPriority") boolean searchPriority,
            Sort sort
    );

}
