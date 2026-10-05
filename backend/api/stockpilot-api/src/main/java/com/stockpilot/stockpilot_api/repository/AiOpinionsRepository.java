package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.AiOpinions;
import org.jspecify.annotations.NonNull;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AiOpinionsRepository extends JpaRepository<AiOpinions, String> {
    Optional<AiOpinions> findById(@NonNull String stockCode);
}
