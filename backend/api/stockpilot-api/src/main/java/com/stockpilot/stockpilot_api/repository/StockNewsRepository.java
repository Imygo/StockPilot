package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.dto.StockNewsResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class StockNewsRepository {
    private final JdbcTemplate jdbc;

    public Optional<String> findLatestModelVersion(String stockCode) {
        List<String> versions = jdbc.queryForList("""
                SELECT model_version
                FROM news_target_predictions
                WHERE stock_code = ?
                ORDER BY created_at DESC, model_version DESC
                LIMIT 1
                """, String.class, stockCode);

        return versions.stream().findFirst();
    }

    public List<StockNewsResponse> findNews(
            String stockCode, String modelVersion, int limit
    ) {
        return jdbc.query("""
                SELECT article_id, stock_code, stock_name,
                       title, description, url, published_at,
                       label, p_negative, p_neutral, p_positive,
                       model_version, quality_json
                FROM news_target_predictions
                WHERE stock_code = ? AND model_version = ?
                ORDER BY published_at DESC, article_id DESC
                LIMIT ?
                """,
                (rs, rowNum) -> new StockNewsResponse(
                        rs.getString("article_id"),
                        rs.getString("stock_code"),
                        rs.getString("stock_name"),
                        rs.getString("title"),
                        rs.getString("description"),
                        rs.getString("url"),
                        rs.getObject("published_at", LocalDateTime.class)
                                .atOffset(ZoneOffset.UTC),
                        rs.getString("label"),
                        rs.getDouble("p_negative"),
                        rs.getDouble("p_neutral"),
                        rs.getDouble("p_positive"),
                        rs.getString("model_version"),
                        rs.getString("quality_json")
                ),
                stockCode, modelVersion, limit);
    }
}