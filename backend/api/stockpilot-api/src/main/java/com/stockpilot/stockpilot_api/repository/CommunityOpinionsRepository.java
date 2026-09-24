package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.CommunityOpinions;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CommunityOpinionsRepository extends JpaRepository<CommunityOpinions, String> {
}
