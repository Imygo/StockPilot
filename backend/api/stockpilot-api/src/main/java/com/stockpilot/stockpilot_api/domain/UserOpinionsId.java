package com.stockpilot.stockpilot_api.domain;

import java.io.Serial;
import java.io.Serializable;
import java.time.*;
import java.util.Objects;

public class UserOpinionsId implements Serializable {
    @Serial
    private static final long serialVersionUID = 1L;
    public String stock_code;
    public String user_id;

    public UserOpinionsId() {}

    public UserOpinionsId(String stock_code, String user_id) {
        this.stock_code = stock_code;
        this.user_id = user_id;
    }

    @Override
    public boolean equals(Object other) {
        if (this == other) return true;
        if (!(other instanceof UserOpinionsId that)) return false;
        return Objects.equals(stock_code, that.stock_code)
            && Objects.equals(user_id, that.user_id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(stock_code, user_id);
    }
}
