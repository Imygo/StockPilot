package com.stockpilot.stockpilot_api.domain;

import jakarta.persistence.*;

@Entity
@Table(name = "community_opinions")
public class CommunityOpinions {
    @Id
    @Column(name = "stock_code", nullable = false, length = 15)
    public String stock_code;
    @Column(name = "buy", nullable = false)
    public Integer buy = 0;
    @Column(name = "neutral", nullable = false)
    public Integer neutral = 0;
    @Column(name = "sell", nullable = false)
    public Integer sell = 0;
}
