package com.stockpilot.stockpilot_api.config;

import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            GoogleLoginSuccessHandler googleLoginSuccessHandler,
            @Value("${app.frontend-url}") String frontendUrl
    ) throws Exception {

        http.authorizeHttpRequests(auth -> auth
                .requestMatchers(
                        "/api/users",
                        "/api/users/exists",
                        "/api/users/me",
                        "/api/users/csrf",
                        "/oauth2/**",
                        "/login/**",
                        "/error"
                ).permitAll()

                // 현재 프로젝트의 HttpSession 기반 사용자 확인 유지
                .requestMatchers("/api/**").access((authentication, context) -> {
                    HttpSession session =
                            context.getRequest().getSession(false);

                    boolean hasUser = session != null
                            && session.getAttribute("userId") instanceof String;

                    return new AuthorizationDecision(hasUser);
                })

                .anyRequest().denyAll()
        );

        http.oauth2Login(oauth -> oauth
                .loginPage(frontendUrl + "/register")
                .successHandler(googleLoginSuccessHandler)
                .failureUrl(frontendUrl + "/register?error=google")
        );

        http.requestCache(cache -> cache.disable());

        // API 요청은 로그인 HTML로 이동시키지 않고 401 반환
        http.exceptionHandling(errors -> errors
                .authenticationEntryPoint((request, response, exception) ->
                        response.setStatus(401))
        );

        http.logout(logout -> logout
                .logoutUrl("/api/users/logout")
                .invalidateHttpSession(true)
                .clearAuthentication(true)
                .deleteCookies("JSESSIONID")
                .logoutSuccessHandler((request, response, authentication) ->
                        response.setStatus(204))
        );

        // CSRF 보호는 기본 활성화 상태로 유지합니다.
        return http.build();
    }
}
