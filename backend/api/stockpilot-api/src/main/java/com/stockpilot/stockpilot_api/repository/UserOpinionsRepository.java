package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.UserOpinions;
import com.stockpilot.stockpilot_api.domain.UserOpinionsId;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserOpinionsRepository extends JpaRepository<UserOpinions, UserOpinionsId> {

}
