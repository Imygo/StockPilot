package com.stockpilot.stockpilot_api.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class UserRegisterRequest {
    @NotBlank(message = "아이디는 필수로 입력해야 합니다.")
    private String userId;
}
