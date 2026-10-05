package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.CommunityOpinions;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface CommunityOpinionsRepository extends JpaRepository<CommunityOpinions, String> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("""
    SELECT c
    FROM CommunityOpinions c
    WHERE c.stock_code = :stockCode
    """)
    Optional<CommunityOpinions> findForUpdate(
            @Param("stockCode") String stockCode
    );
}
