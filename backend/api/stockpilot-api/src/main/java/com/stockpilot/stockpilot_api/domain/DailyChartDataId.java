package com.stockpilot.stockpilot_api.domain;

import java.io.Serial;
import java.io.Serializable;
import java.time.*;
import java.util.Objects;

public class DailyChartDataId implements Serializable {
    @Serial
    private static final long serialVersionUID = 1L;
    public String stock_code;
    public LocalDate trade_date;

    public DailyChartDataId() {}

    public DailyChartDataId(String stock_code, LocalDate trade_date) {
        this.stock_code = stock_code;
        this.trade_date = trade_date;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (!(other instanceof DailyChartDataId that)) return false;
        return Objects.equals(stock_code, that.stock_code)
            && Objects.equals(trade_date, that.trade_date);
    }

    @Override
    public int hashCode() {
        return Objects.hash(stock_code, trade_date);
    }
}
