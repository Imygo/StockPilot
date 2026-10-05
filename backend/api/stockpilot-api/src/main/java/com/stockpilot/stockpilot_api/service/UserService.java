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
    public void register(UserRegisterRequest request){
        String userId = request.getUserId();

        if (userId == null || userId.isBlank()){
            throw new IllegalArgumentException("사용자 ID는 필수입니다.");
        }

        if(usersRepository.existsById(userId)){
            throw new DuplicateUserIdException(userId);
        }

        Users user = new Users();

        user.user_id = userId;

        usersRepository.save(user);
    }

    // 유저가 존재하는지만 확인하는 함수
    // 회원가입은 아니지만 의견구분을 위해 userId는 필요하므로..
    // 각 계층간 DTO로 전달되어야 한다면 파라미터는 String userId가 아닌 FindUserRequest가 될 것이다.

    @Transactional(readOnly = true)
    public boolean existingUser(FindUserRequest request) {
        return usersRepository.existsById(request.getUserId());
    }

}
