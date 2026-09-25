package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.AiOpinions;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AiOpinionsRepository extends JpaRepository<AiOpinions, String> {
}
