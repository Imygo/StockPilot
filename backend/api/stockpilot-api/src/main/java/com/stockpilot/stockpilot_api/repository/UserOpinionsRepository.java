package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.UserOpinions;
import com.stockpilot.stockpilot_api.domain.UserOpinionsId;
import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import org.antlr.v4.runtime.misc.Pair;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserOpinionsRepository extends JpaRepository<UserOpinions, UserOpinionsId> {
}
