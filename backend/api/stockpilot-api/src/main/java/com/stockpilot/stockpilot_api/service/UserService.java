package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.Users;
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
    public void register(UsersRepository request){
        String userId = request.getUserId();

        if(usersRepository.existsByUserId(userId)){
            throw new DuplicateUserIdException(userId);
        }

        Users user = new Users();

        user.user_id = userId;

        usersRepository.save(user);

    }
}
