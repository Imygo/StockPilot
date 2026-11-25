package com.stockpilot.stockpilot_api.service;

import com.stockpilot.stockpilot_api.domain.Users;
import com.stockpilot.stockpilot_api.dto.UserRegisterRequest;
import com.stockpilot.stockpilot_api.repository.UsersRepository;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class GoogleUserIdentityTest {
    @Test
    void googleAccountCannotBeEnteredThroughLocalNameForm() {
        UsersRepository repository = mock(UsersRepository.class);
        Users googleUser = new Users();
        googleUser.user_id = "g_existing";
        googleUser.auth_provider = "GOOGLE";
        when(repository.findById("g_existing")).thenReturn(Optional.of(googleUser));
        UserRegisterRequest request = new UserRegisterRequest();
        request.setUserId("g_existing");
        var service = new UserService(repository);

        var exception = assertThrows(IllegalArgumentException.class, () -> service.register(request));
        assertTrue(exception.getMessage().contains("Google"));
    }

    @Test
    void repeatedGoogleLoginUsesSubjectRatherThanDisplayNameForIdentity() {
        UsersRepository repository = mock(UsersRepository.class);
        Users existing = new Users();
        existing.user_id = "g_stable-id";
        existing.auth_provider = "GOOGLE";
        when(repository.findByGoogleSub("stable-sub")).thenReturn(Optional.of(existing));
        var service = new UserService(repository);

        assertEquals("g_stable-id", service.findOrCreateGoogleUser("stable-sub", "이전 이름").user_id);
        assertEquals("g_stable-id", service.findOrCreateGoogleUser("stable-sub", "새 이름").user_id);
        verify(repository).upsertGoogleUser(startsWith("g_"), eq("stable-sub"), eq("이전 이름"));
        verify(repository).upsertGoogleUser(startsWith("g_"), eq("stable-sub"), eq("새 이름"));
    }
}
