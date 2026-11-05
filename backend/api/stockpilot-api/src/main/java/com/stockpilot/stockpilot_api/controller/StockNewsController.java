package com.stockpilot.stockpilot_api.controller;

import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/** Reads the additive news table through the existing StockPilot datasource. */
@RestController
public class StockNewsController {
    private final JdbcTemplate jdbc;

    public StockNewsController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public record NewsPrediction(String articleId, String stockCode, String stockName,
            String title, String description, String url, OffsetDateTime publishedAt,
            String label, double negative, double neutral, double positive,
            String modelVersion, String qualityJson) {}

    @GetMapping("/api/stocks/{stockCode}/news")
    public List<NewsPrediction> news(@PathVariable("stockCode") String stockCode,
            @RequestParam(name="limit", defaultValue="30") int limit,
            @RequestParam(name="modelVersion", required=false) String modelVersion) {
        if (!stockCode.matches("[0-9A-Z]{6}") || limit < 1 || limit > 100
                || (modelVersion != null && !modelVersion.matches("[0-9a-f]{64}"))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid stockCode, limit or modelVersion");
        }
        String version = modelVersion;
        if (version == null) {
            List<String> versions = jdbc.queryForList(
                "SELECT model_version FROM news_target_predictions WHERE stock_code=? "
                + "ORDER BY created_at DESC, model_version DESC LIMIT 1", String.class, stockCode);
            if (versions.isEmpty()) return List.of();
            version = versions.get(0);
        }
        return jdbc.query("SELECT article_id,stock_code,stock_name,title,description,url,published_at,"
            + "label,p_negative,p_neutral,p_positive,model_version,quality_json "
            + "FROM news_target_predictions WHERE stock_code=? AND model_version=? "
            + "ORDER BY published_at DESC,article_id DESC LIMIT ?",
            (rs, rowNum) -> new NewsPrediction(rs.getString("article_id"),rs.getString("stock_code"),
                rs.getString("stock_name"),rs.getString("title"),rs.getString("description"),rs.getString("url"),
                rs.getObject("published_at", LocalDateTime.class).atOffset(ZoneOffset.UTC),rs.getString("label"),
                rs.getDouble("p_negative"),rs.getDouble("p_neutral"),rs.getDouble("p_positive"),
                rs.getString("model_version"),rs.getString("quality_json")),stockCode,version,limit);
    }
}
