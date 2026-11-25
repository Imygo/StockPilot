package com.stockpilot.stockpilot_api.config;

import com.stockpilot.stockpilot_api.controller.UserController;
import com.stockpilot.stockpilot_api.service.UserService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.client.registration.ClientRegistration;
import org.springframework.security.oauth2.client.registration.ClientRegistrationRepository;
import org.springframework.security.oauth2.client.registration.InMemoryClientRegistrationRepository;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.web.FilterChainProxy;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.junit.jupiter.SpringExtension;
import org.springframework.test.context.web.WebAppConfiguration;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

import static org.hamcrest.Matchers.startsWith;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(SpringExtension.class)
@WebAppConfiguration
@ContextConfiguration(classes = GoogleSecurityFlowTest.TestConfig.class)
@TestPropertySource(properties = "app.frontend-url=http://localhost:5173")
class GoogleSecurityFlowTest {
    @Configuration
    @EnableWebSecurity
    @EnableWebMvc
    @Import({SecurityConfig.class, GoogleLoginSuccessHandler.class, UserController.class})
    static class TestConfig {
        @Bean UserService userService() { return mock(UserService.class); }
        @Bean ClientRegistrationRepository clients() {
            return new InMemoryClientRegistrationRepository(ClientRegistration.withRegistrationId("google")
                    .clientId("test-client").clientSecret("test-secret")
                    .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                    .redirectUri("http://localhost:8080/login/oauth2/code/google")
                    .scope("openid", "profile", "email")
                    .authorizationUri("https://accounts.google.com/o/oauth2/v2/auth")
                    .tokenUri("https://oauth2.googleapis.com/token")
                    .jwkSetUri("https://www.googleapis.com/oauth2/v3/certs")
                    .userInfoUri("https://openidconnect.googleapis.com/v1/userinfo")
                    .userNameAttributeName("sub").clientName("Google").build());
        }
    }

    @Autowired WebApplicationContext context;
    @Autowired FilterChainProxy springSecurityFilterChain;
    @Autowired UserService service;
    MockMvc mvc;

    @BeforeEach void setup() {
        reset(service);
        mvc = MockMvcBuilders.webAppContextSetup(context).addFilters(springSecurityFilterChain).build();
    }

    @Test void loginStartsAuthorizationCodeFlow() throws Exception {
        mvc.perform(get("/oauth2/authorization/google"))
                .andExpect(status().is3xxRedirection())
                .andExpect(header().string("Location", startsWith("https://accounts.google.com/")));
    }

    @Test void invalidCallbackDoesNotEstablishSessionIdentity() throws Exception {
        var result = mvc.perform(get("/login/oauth2/code/google")
                        .param("code", "invalid").param("state", "unknown"))
                .andExpect(redirectedUrl("http://localhost:5173/register?error=google"))
                .andReturn();
        var session = result.getRequest().getSession(false);
        assertTrue(session == null || session.getAttribute("userId") == null);
        verifyNoInteractions(service);
    }

    @Test void anonymousApiGets401RatherThanGoogleHtml() throws Exception {
        mvc.perform(get("/api/stocks")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/users/me")).andExpect(status().isUnauthorized());
    }

    @Test void postWithoutCsrfIsRejected() throws Exception {
        mvc.perform(post("/api/users").contentType("application/json")
                .content("{\"userId\":\"moon\"}"))
                .andExpect(status().isForbidden());
        verifyNoInteractions(service);
    }

    @Test void csrfProtectedLocalLoginRotatesSessionAndRemainsCompatible() throws Exception {
        when(service.register(any())).thenReturn("moon");
        var tokenResult = mvc.perform(get("/api/users/csrf")).andExpect(status().isOk()).andReturn();
        var oldSession = (MockHttpSession) tokenResult.getRequest().getSession(false);
        var token = (CsrfToken) tokenResult.getRequest().getAttribute(CsrfToken.class.getName());
        var loginResult = mvc.perform(post("/api/users").session(oldSession)
                        .header(token.getHeaderName(), token.getToken())
                        .contentType("application/json").content("{\"userId\":\"moon\"}"))
                .andExpect(status().isOk()).andReturn();
        var session = (MockHttpSession) loginResult.getRequest().getSession(false);
        assertNotEquals(oldSession.getId(), session.getId());
        mvc.perform(get("/api/users/me").session(session))
                .andExpect(jsonPath("$.userId").value("moon"))
                .andExpect(jsonPath("$.authProvider").value("LOCAL"));
    }

    @Test void googleIdentityIsReturnedAndLogoutInvalidatesSession() throws Exception {
        var session = new MockHttpSession();
        session.setAttribute("userId", "g_123");
        session.setAttribute("displayName", "홍길동");
        session.setAttribute("authProvider", "GOOGLE");
        mvc.perform(get("/api/users/me").session(session))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.displayName").value("홍길동"))
                .andExpect(jsonPath("$.userId").value("g_123"));
        var result = mvc.perform(get("/api/users/csrf").session(session)).andReturn();
        var token = (CsrfToken) result.getRequest().getAttribute(CsrfToken.class.getName());
        mvc.perform(post("/api/users/logout").session(session)
                        .header(token.getHeaderName(), token.getToken()))
                .andExpect(status().isNoContent());
        assertTrue(session.isInvalid());
    }
}
