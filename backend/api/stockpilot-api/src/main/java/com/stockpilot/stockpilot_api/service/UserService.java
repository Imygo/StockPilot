package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.Users;
import com.stockpilot.stockpilot_api.dto.FindUserRequest;
import com.stockpilot.stockpilot_api.dto.UserRegisterRequest;
import com.stockpilot.stockpilot_api.global.exception.DuplicateUserIdException;
import com.stockpilot.stockpilot_api.repository.UsersRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

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

        return user.user_id;
    }

    // 유저가 존재하는지만 확인하는 함수
    // 회원가입은 아니지만 의견구분을 위해 userId는 필요하므로..
    // 각 계층간 DTO로 전달되어야 한다면 파라미터는 String userId가 아닌 FindUserRequest가 될 것이다.

    @Transactional(readOnly = true)
    public boolean existingUser(FindUserRequest request) {
        return usersRepository.existsById(request.getUserId());
    }

}
