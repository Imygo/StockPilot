package com.stockpilot.stockpilot_api.domain;

import jakarta.persistence.*;
import java.time.*;
import org.hibernate.annotations.Generated;
import org.hibernate.generator.EventType;

@Entity
@Table(name = "users")
public class Users {
    @Id
    @Column(name = "user_id", nullable = false, length = 50)
    public String user_id;
    @Generated(event = EventType.INSERT)
    @Column(name = "created_at", insertable = false, updatable = false, columnDefinition = "TIMESTAMP")
    public LocalDateTime created_at;
}
