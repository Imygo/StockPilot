package com.stockpilot.stockpilot_api.domain;

import jakarta.persistence.*;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import java.time.*;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

@Entity
@Table(name = "user_opinions")
@IdClass(UserOpinionsId.class)
public class UserOpinions {
    @Id
    @Column(name = "stock_code", nullable = false, length = 15)
    public String stock_code;
    @Id
    @Column(name = "user_id", nullable = false, length = 50)
    public String user_id;
    @Convert(converter = OpinionTypeConverter.class)
    @Column(name = "opinion", nullable = false)
    public OpinionType opinion = OpinionType.NEUTRAL;
    @Generated(event = {EventType.INSERT, EventType.UPDATE})
    @Column(name = "updated_at", insertable = false, updatable = false, columnDefinition = "TIMESTAMP")
    public LocalDateTime updated_at;
}
