package com.stockpilot.stockpilot_api.domain;

import java.io.Serial;
import java.io.Serializable;
import java.time.*;
import java.util.Objects;

public class MinuteChartDataId implements Serializable {
    @Serial
    private static final long serialVersionUID = 1L;
    public String stock_code;
    public LocalDateTime candle_start;

    public MinuteChartDataId() {}

    public MinuteChartDataId(String stock_code, LocalDateTime candle_start) {
        this.stock_code = stock_code;
        this.candle_start = candle_start;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (!(other instanceof MinuteChartDataId that)) return false;
        return Objects.equals(stock_code, that.stock_code)
            && Objects.equals(candle_start, that.candle_start);
    }

    @Override
    public int hashCode() {
        return Objects.hash(stock_code, candle_start);
    }
}
