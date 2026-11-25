package com.stockpilot.stockpilot_api.config;

import com.stockpilot.stockpilot_api.domain.Users;
import com.stockpilot.stockpilot_api.service.UserService;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.core.oidc.user.OidcUser;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class GoogleLoginSuccessHandlerTest {
    @Test
    void storesInternalIdAndDisplayNameSeparately() throws Exception {
        UserService service = mock(UserService.class);
        OidcUser principal = mock(OidcUser.class);
        Authentication authentication = mock(Authentication.class);
        when(authentication.getPrincipal()).thenReturn(principal);
        when(principal.getSubject()).thenReturn("google-sub-123");
        when(principal.getFullName()).thenReturn("홍길동");
        Users user = new Users();
        user.user_id = "g_existing-user";
        user.display_name = "홍길동";
        when(service.findOrCreateGoogleUser("google-sub-123", "홍길동")).thenReturn(user);

        var request = new MockHttpServletRequest();
        request.getSession().setAttribute("userId", "old-local-user");
        var response = new MockHttpServletResponse();
        new GoogleLoginSuccessHandler(service, "http://localhost:5173/")
                .onAuthenticationSuccess(request, response, authentication);

        assertEquals("g_existing-user", request.getSession().getAttribute("userId"));
        assertEquals("홍길동", request.getSession().getAttribute("displayName"));
        assertEquals("GOOGLE", request.getSession().getAttribute("authProvider"));
        assertEquals("http://localhost:5173/", response.getRedirectedUrl());
    }

    @Test
    void databaseFailureClearsPriorSessionAndAuthentication() throws Exception {
        UserService service = mock(UserService.class);
        OidcUser principal = mock(OidcUser.class);
        Authentication authentication = mock(Authentication.class);
        when(authentication.getPrincipal()).thenReturn(principal);
        when(principal.getSubject()).thenReturn("sub");
        when(service.findOrCreateGoogleUser("sub", null)).thenThrow(new IllegalStateException());
        var request = new MockHttpServletRequest();
        request.getSession().setAttribute("userId", "previous-user");
        SecurityContextHolder.getContext().setAuthentication(authentication);
        var response = new MockHttpServletResponse();
        try {
            new GoogleLoginSuccessHandler(service, "http://localhost:5173")
                    .onAuthenticationSuccess(request, response, authentication);
            assertNull(request.getSession(false));
            assertNull(SecurityContextHolder.getContext().getAuthentication());
            assertEquals("http://localhost:5173/register?error=google", response.getRedirectedUrl());
        } finally {
            SecurityContextHolder.clearContext();
        }
    }
}
