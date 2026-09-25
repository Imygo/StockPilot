package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.Stock;
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
    List<Stock> searchByKeyword(@Param("keyword") String keyword);
}
