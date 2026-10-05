package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.CommunityOpinions;
import com.stockpilot.stockpilot_api.domain.UserOpinions;
import com.stockpilot.stockpilot_api.domain.UserOpinionsId;
import com.stockpilot.stockpilot_api.dto.CommunityOpinionViewResponse;
import com.stockpilot.stockpilot_api.dto.CommunityOpinionsResponse;
import com.stockpilot.stockpilot_api.dto.UserOpinionRequest;
import com.stockpilot.stockpilot_api.repository.CommunityOpinionsRepository;
import com.stockpilot.stockpilot_api.repository.StockRepository;
import com.stockpilot.stockpilot_api.repository.UserOpinionsRepository;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import com.stockpilot.stockpilot_api.repository.UsersRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.NoSuchElementException;

@Service
@RequiredArgsConstructor
public class OpinionService {
    private final UsersRepository usersRepository;
    private final StockRepository stockRepository;
    private final UserOpinionsRepository userOpinionsRepository;
    private final CommunityOpinionsRepository communityOpinionsRepository;

    // 1. 사용자가 특정 주식에 의견을 표했는지 확인하는 로직.
    // 이미 등록한 의견이 있다면, 선택한 의견을 표시함 ( 이건 프론트엔드 )
    // 무슨 의견을 냈는지에 대한 데이터를 전송하긴 해야함
    // 그렇지 않다면 의견을 선택하도록 버튼을 제시
    @Transactional(readOnly = true)
    public OpinionType opinionCheck(String userId, String stockCode){

        // 사용자 의견 테이블의 PK는 stock_code + user_id이므로 해당 조건으로 검색한다.
        // 키쌍
        UserOpinionsId id = new UserOpinionsId(stockCode, userId);

        // 둘 다 오류는 아님
        // 반환하는 값이 있어야 함.
        // 투표했는지 여부를 확인하는 컬럼을 추가할 필요가 있을 것 같다.
        // pk 확인결과 투표여부가 N이면 Null 그렇지 않으면 OpinionType을 반환하면 되나?

        // 행이 없거나 N이면 미투표이므로 null
        // Y이면 저장된 의견 반환
        // 명시적으로 중립을 선택했다면 NEUTRAL 반환
        // 프론트엔드에 응답 DTO로 { "voted": false, "opinion": null } 전달
        return userOpinionsRepository.findById(id)
                .filter(vote -> "Y".equals(vote.voteYn))
                .map(vote -> vote.opinion)
                .orElse(null);
    }

    @Transactional
    public void saveOpinion(
            String userId,
            String stockCode,
            UserOpinionRequest request
    ){
        OpinionType newOpinion = request.getOpinion();

        if(newOpinion == null){
            throw new IllegalArgumentException("의견을 선택해야 합니다.");
        }

        var lockedCounts =
                communityOpinionsRepository.findForUpdate(stockCode);

        // 의견 서비스에서 종목 존재여부를 확인한다.
        // 존재하지 않는 종목과 존재하지만 집계행이 누락된 종목은 구분
        // 종목 자체가 없는 경우
        if(!stockRepository.existsById(stockCode)){
            throw new NoSuchElementException("존재하지 않는 종목입니다.");
        }

        // 종목은 있지만 집계 행이 누락된 경우
        CommunityOpinions counts =
                communityOpinionsRepository.findForUpdate(stockCode)
                        .orElseThrow(()->
                                new IllegalStateException("집계 행이 없습니다."));

        if(!usersRepository.existsById(userId)){
            throw new IllegalArgumentException("등록되지 않은 사용자입니다.");
        }

        UserOpinionsId id = new UserOpinionsId(stockCode, userId);
        UserOpinions vote = userOpinionsRepository.findById(id)
                .orElse(null);

        // N인 행의 opinion 값은 이전 투표로 집계하면 안된다
        OpinionType oldOpinion =
                vote != null && "Y".equals(vote.voteYn)
                        ? vote.opinion
                        : null;

        // 같은 의견을 다시 보내도 집계는 증가하지 않는다
        if (oldOpinion == newOpinion) {
            return;
        }

        if (vote == null) {
            vote = new UserOpinions();
            vote.stock_code = stockCode;
            vote.user_id = userId;
        }

        if (oldOpinion != null) {
            adjustCount(counts, oldOpinion, -1);
        }
        adjustCount(counts, newOpinion, 1);

        vote.opinion = newOpinion;
        vote.voteYn = "Y";

        userOpinionsRepository.save(vote);
        communityOpinionsRepository.save(counts);
    }

    private void adjustCount(
            CommunityOpinions counts,
            OpinionType opinion,
            int amount
    ) {
        switch (opinion) {
            case BUY -> counts.buy += amount;
            case NEUTRAL -> counts.neutral += amount;
            case SELL -> counts.sell += amount;
        }
    }


    // 2. 이미 등록된 의견들(커뮤니티 의견)을 가져오는 로직.
    @Transactional(readOnly = true)
    public CommunityOpinionsResponse getCommunityOpinion(String stockCode){
        CommunityOpinions counts =
                communityOpinionsRepository.findById(stockCode)
                        .orElseThrow(()->
                                new IllegalStateException("집계 행이 없습니다."));

        return new CommunityOpinionsResponse(
                stockCode,
                counts.buy,
                counts.neutral,
                counts.sell
        );
    }

    @Transactional(readOnly = true)
    public CommunityOpinionViewResponse getCommunityView(
            String stockCode,
            String userId
    ) {
        CommunityOpinionsResponse counts = getCommunityOpinion(stockCode);

        OpinionType myOpinion = userId == null
                ? null
                : opinionCheck(userId, stockCode);

        return new CommunityOpinionViewResponse(
                stockCode,
                counts.getBuy(),
                counts.getNeutral(),
                counts.getSell(),
                (long) counts.getBuy() + counts.getNeutral() + counts.getSell(),
                myOpinion != null,
                myOpinion
        );
    }

    @Transactional
    public CommunityOpinionViewResponse saveAndGetView(
            String userId,
            String stockCode,
            UserOpinionRequest request
    ) {
        saveOpinion(userId, stockCode, request);
        return getCommunityView(stockCode, userId);
    }
}
