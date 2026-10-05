package com.stockpilot.stockpilot_api.domain;

import com.stockpilot.stockpilot_api.service.AiOpinionService;
import jakarta.persistence.*;
import java.time.*;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

@Entity
@Table(name = "ai_opinions")
public class AiOpinions {
    @Id
    @Column(name = "stock_code", nullable = false, length = 15)
    public String stock_code;
    @Column(name = "invest_opinion", nullable = true, length = 100)
    public String invest_opinion;
    @Generated(event = {EventType.INSERT, EventType.UPDATE})
    @Column(name = "updated_at", insertable = false, updatable = false, columnDefinition = "TIMESTAMP")
    public LocalDateTime updated_at;
}
