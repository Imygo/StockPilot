package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.AiOpinions;
import com.stockpilot.stockpilot_api.dto.AiOpinionResponse;
import com.stockpilot.stockpilot_api.repository.AiOpinionsRepository;
import com.stockpilot.stockpilot_api.repository.StockRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.NoSuchElementException;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class AiOpinionService {

    private final AiOpinionsRepository aiOpinionsRepository;
    private final StockRepository stockRepository;

    @Transactional(readOnly = true)
    public AiOpinionResponse getAiOpinion(String stockCode){

        if(stockCode == null || stockCode.isBlank()){
            throw new IllegalArgumentException("종목코드는 필수입니다.");
        }

        // 주식코드를 받은 후, 존재하는 코드인지 확인하는 절차
        if(!stockRepository.existsById(stockCode)){
            throw new NoSuchElementException("유효하지 않은 주식코드입니다.");
        }

        // 종목은 있지만 AI의견이 아직 없으면 {"aiOpinion":null}을 반환
        return aiOpinionsRepository.findById(stockCode)
                .map(this::toResponse)
                .orElseGet(()->new AiOpinionResponse(null));
    }

    //
    private AiOpinionResponse toResponse(AiOpinions entity){
        return new AiOpinionResponse(
                entity.invest_opinion
        );
    }

}
