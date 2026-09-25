package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.Users;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UsersRepository extends JpaRepository <Users,String> {
    boolean existsByUserId(String userId);

    String getUserId();
}
