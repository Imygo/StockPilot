package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.Users;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface UsersRepository extends JpaRepository <Users,String> {
    @Modifying
    @Query(value = """
        INSERT INTO users (user_id)
        VALUES (:userId)
        ON DUPLICATE KEY UPDATE user_id = user_id
        """, nativeQuery = true)
    void insertIfMissing(@Param("userId") String userId);
}
