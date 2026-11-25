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
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {
    private final UserService userService;

    // 사용자등록을 위한 api경로 설정
    //  POST /api/users
    //  GET /api/users/exists?userId=user001
    //    @SessionAttribute : 서버 세션에 저장한 값을 현재 요청에서 꺼내는 역할
    //    session.setAttribute(“userId”, request.getUserId());에서 유저아이디를 등록 및 저장
    //    OpinionController에서 사용함
    //    -> required = false이므로 세션에 값이 없다면 userId = null
    @PostMapping
    public ResponseEntity<Map<String, String>> registerUser(
            @Valid @RequestBody UserRegisterRequest request,
            HttpServletRequest httpRequest
    ) {
        String userId = userService.register(request);

        // 이전 사용자의 세션 정보가 남지 않도록 새 세션을 만듭니다.
        HttpSession oldSession = httpRequest.getSession(false);
        if (oldSession != null) {
            oldSession.invalidate();
        }

        HttpSession session = httpRequest.getSession(true);
        session.setAttribute("userId", userId);
        session.setAttribute("displayName", userId);
        session.setAttribute("authProvider", "LOCAL");

        return ResponseEntity.ok(Map.of(
                "userId", userId,
                "displayName", userId,
                "authProvider", "LOCAL"
        ));
    }

    // 사용자가 존재하는지 확인하는 것.
    // 추후에 로그인 로직으로 확장될 수 있음
    @GetMapping("/exists")
    public boolean existsUser(
            @Valid @ModelAttribute FindUserRequest request
    ) {
        return userService.existingUser(request);
    }

    @GetMapping("/me")
    public ResponseEntity<Map<String, String>> currentUser(
            HttpServletRequest request
    ) {
        HttpSession session = request.getSession(false);

        if (session == null ||
                !(session.getAttribute("userId") instanceof String userId)) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        String displayName = session.getAttribute("displayName") instanceof String name
                ? name
                : userId;

        String authProvider = session.getAttribute("authProvider") instanceof String provider
                ? provider
                : "LOCAL";

        return ResponseEntity.ok()
                .header("Cache-Control", "no-store")
                .body(Map.of(
                        "userId", userId,
                        "displayName", displayName,
                        "authProvider", authProvider
                ));
    }
}
