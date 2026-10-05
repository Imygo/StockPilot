package com.stockpilot.stockpilot_api.domain;

import jakarta.persistence.*;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import java.time.*;

import lombok.Builder;
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
    // 의견을 제시하지 않으면 자연스레 null 값을 가지게끔 설정해야 함
    @Column(name = "opinion", nullable = true)
    public OpinionType opinion;
    @Column(name = "vote_yn", nullable = false, length = 1)
    public String voteYn = "N";
    @Generated(event = {EventType.INSERT, EventType.UPDATE})
    @Column(name = "updated_at", insertable = false, updatable = false, columnDefinition = "TIMESTAMP")
    public LocalDateTime updated_at;
}
