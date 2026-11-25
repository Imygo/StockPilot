package com.stockpilot.stockpilot_api.config;

import com.stockpilot.stockpilot_api.domain.Users;
import com.stockpilot.stockpilot_api.service.UserService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
public class GoogleLoginSuccessHandler implements AuthenticationSuccessHandler {
    private static final Logger log = LoggerFactory.getLogger(GoogleLoginSuccessHandler.class);
    private final UserService userService;
    private final String frontendUrl;

    public GoogleLoginSuccessHandler(UserService userService,
                                     @Value("${app.frontend-url}") String frontendUrl) {
        this.userService = userService;
        this.frontendUrl = frontendUrl.replaceAll("/+$", "");
    }

    @Override
    public void onAuthenticationSuccess(HttpServletRequest request,
                                        HttpServletResponse response,
                                        Authentication authentication) throws IOException {
        try {
            OidcUser principal = (OidcUser) authentication.getPrincipal();
            Users user = userService.findOrCreateGoogleUser(
                    principal.getSubject(), principal.getFullName());
            HttpSession session = request.getSession(true);
            session.setAttribute("userId", user.user_id);
            session.setAttribute("displayName", user.display_name);
            session.setAttribute("authProvider", "GOOGLE");
        } catch (RuntimeException exception) {
            // OAuth 인증 이후 DB 저장 실패 시 이전 사용자/인증 세션을 남기지 않습니다.
            log.error("Google user persistence failed ({})", exception.getClass().getSimpleName());
            HttpSession session = request.getSession(false);
            if (session != null) session.invalidate();
            SecurityContextHolder.clearContext();
            response.sendRedirect(frontendUrl + "/register?error=google");
            return;
        }
        response.sendRedirect(frontendUrl + "/");
    }
}
