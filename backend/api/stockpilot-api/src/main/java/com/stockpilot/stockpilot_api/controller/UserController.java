package com.stockpilot.stockpilot_api.controller;

import com.stockpilot.stockpilot_api.dto.FindUserRequest;
import com.stockpilot.stockpilot_api.dto.UserRegisterRequest;
import com.stockpilot.stockpilot_api.service.UserService;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {
    private final UserService userService;

    // 사용자등록을 위한 api경로를 설정해야 함
    // /api/user-login이 먼저 있고 기존의 아이디가 없으면 /api/user-login/user-register로 넘어가야 할지도 모름
    // POST /api/users
    // GET /api/users/exists?userId=user001
    @PostMapping
    public ResponseEntity<Void> registerUser(
            @Valid @RequestBody UserRegisterRequest request,
            HttpSession session){
        userService.register(request);

        session.setAttribute("userId", request.getUserId());

        return ResponseEntity.status(HttpStatus.CREATED).build();
    }

    // 사용자가 존재하는지 확인하는 것.
    // 추후에 로그인 로직으로 확장될 수 있음
    @GetMapping("/exists")
    public boolean existsUser(
            @Valid @ModelAttribute FindUserRequest request
    ) {
        return userService.existingUser(request);
    }
}
