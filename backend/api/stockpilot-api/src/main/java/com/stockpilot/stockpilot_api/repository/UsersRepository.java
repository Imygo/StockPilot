package com.stockpilot.stockpilot_api.repository;

import com.stockpilot.stockpilot_api.domain.Users;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.Optional;

public interface UsersRepository extends JpaRepository <Users,String> {
    @Modifying
    @Query(value = """
        INSERT INTO users (user_id)
        VALUES (:userId)
        ON DUPLICATE KEY UPDATE user_id = user_id
        """, nativeQuery = true)
    void insertIfMissing(@Param("userId") String userId);

    @Query("""
    SELECT u
    FROM Users u
    WHERE u.google_sub = :sub
    """)
    Optional<Users> findByGoogleSub(@Param("sub") String sub);

    @Modifying
    @Query(value = """
    INSERT INTO users (
        user_id, auth_provider, google_sub, display_name
    )
    VALUES (
        :userId, 'GOOGLE', :sub, :displayName
    )
    ON DUPLICATE KEY UPDATE display_name = :displayName
    """, nativeQuery = true)
    void upsertGoogleUser(
            @Param("userId") String userId,
            @Param("sub") String sub,
            @Param("displayName") String displayName
    );
}
