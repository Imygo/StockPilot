package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.Users;
import com.stockpilot.stockpilot_api.dto.FindUserRequest;
import com.stockpilot.stockpilot_api.dto.UserRegisterRequest;
import com.stockpilot.stockpilot_api.repository.UsersRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UserService {
    private final UsersRepository usersRepository;

    @Transactional
    public String register(UserRegisterRequest request) {
        String userId = request.getUserId() == null
                ? ""
                : request.getUserId().strip();

        if (userId.isBlank()) {
            throw new IllegalArgumentException("사용자 ID는 필수입니다.");
        }

        if (userId.length() > 50) {
            throw new IllegalArgumentException("사용자 ID는 50자 이하여야 합니다.");
        }

        usersRepository.insertIfMissing(userId);

        // DB에 저장된 ID를 기준으로 세션을 구성합니다.
        Users user = usersRepository.findById(userId)
                .orElseThrow(() ->
                        new IllegalStateException("사용자 정보를 확인하지 못했습니다.")
                );

        if (!"LOCAL".equals(user.auth_provider)) {
            throw new IllegalArgumentException(
                    "이 계정은 Google 로그인으로 입장해주세요."
            );
        }

        return user.user_id;
    }

    // 유저가 존재하는지만 확인하는 함수
    // 회원가입은 아니지만 의견구분을 위해 userId는 필요하므로..
    // 각 계층간 DTO로 전달되어야 한다면 파라미터는 String userId가 아닌 FindUserRequest가 될 것이다.

    @Transactional(readOnly = true)
    public boolean existingUser(FindUserRequest request) {
        return usersRepository.existsById(request.getUserId());
    }

    @Transactional
    public Users findOrCreateGoogleUser(String sub, String name) {
        if (sub == null || sub.isBlank() || sub.length() > 255) {
            throw new IllegalArgumentException("Google 계정 식별자가 올바르지 않습니다.");
        }

        String displayName = name == null || name.isBlank()
                ? "Google 사용자"
                : name.strip();

        if (displayName.length() > 255) {
            displayName = displayName.substring(0, 255);
        }

        usersRepository.upsertGoogleUser(
                "g_" + UUID.randomUUID(),
                sub,
                displayName
        );

        return usersRepository.findByGoogleSub(sub)
                .orElseThrow(() ->
                        new IllegalStateException("Google 사용자를 확인하지 못했습니다.")
                );
    }

}
