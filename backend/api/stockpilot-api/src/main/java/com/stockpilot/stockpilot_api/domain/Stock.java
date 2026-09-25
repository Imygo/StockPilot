package com.stockpilot.stockpilot_api.domain;

import jakarta.persistence.*;
import com.stockpilot.stockpilot_api.global.enums.Market;
import java.time.*;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

@Entity
@Table(name = "stock")
public class Stock {
    @Id
    @Column(name = "stock_code", nullable = false, length = 15)
    public String stock_code;
    @Column(name = "stock_name", nullable = false, length = 100)
    public String stock_name;
    @Enumerated(EnumType.STRING)
    @Column(name = "market", nullable = true, length = 10)
    public Market market;
    @Column(name = "current_price", nullable = true)
    public Integer current_price;
    // MySQL column names are case-insensitive; marketcap avoids snake_case conversion.
    @Column(name = "marketcap")
    public Long marketCap;
    @Column(name = "change_rate", nullable = true)
    public Double change_rate;
    @Column(name = "change_amount", nullable = true)
    public Double change_amount;
    @Column(name = "volume", nullable = true)
    public Long volume;
    @Generated(event = {EventType.INSERT, EventType.UPDATE})
    @Column(name = "updated_at", insertable = false, updatable = false, columnDefinition = "TIMESTAMP")
    public LocalDateTime updated_at;
}
