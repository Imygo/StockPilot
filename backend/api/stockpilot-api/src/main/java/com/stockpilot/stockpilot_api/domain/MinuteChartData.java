package com.stockpilot.stockpilot_api.domain;

import jakarta.persistence.*;
import java.time.*;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

@Entity
@Table(name = "minute_chart_data")
@IdClass(MinuteChartDataId.class)
public class MinuteChartData {
    @Id
    @Column(name = "stock_code", nullable = false, length = 15)
    public String stock_code;
    @Id
    @Column(name = "candle_start", nullable = false)
    public LocalDateTime candle_start;
    @Column(name = "close_price", nullable = true)
    public Integer close_price;
    @Column(name = "open_price", nullable = true)
    public Integer open_price;
    @Column(name = "high_price", nullable = true)
    public Integer high_price;
    @Column(name = "low_price", nullable = true)
    public Integer low_price;
    @Column(name = "volume", nullable = true)
    public Long volume;
    @Column(name = "change_rate", nullable = true)
    public Double change_rate;
    @Column(name = "change_amount", nullable = true)
    public Double change_amount;
    @Generated(event = EventType.INSERT)
    @Column(name = "updated_at", insertable = false, updatable = false, columnDefinition = "TIMESTAMP")
    public LocalDateTime updated_at;
}
