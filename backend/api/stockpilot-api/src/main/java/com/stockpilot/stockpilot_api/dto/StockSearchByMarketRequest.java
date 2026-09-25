package com.stockpilot.stockpilot_api.dto;

import com.stockpilot.stockpilot_api.global.enums.Market;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class StockSearchByMarketRequest {
    private Market market;

}
