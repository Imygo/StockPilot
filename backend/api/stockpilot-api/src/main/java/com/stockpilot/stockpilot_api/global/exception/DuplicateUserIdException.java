package com.stockpilot.stockpilot_api.global.exception;

public class DuplicateUserIdException extends RuntimeException {
    public DuplicateUserIdException(String userId){
        super("이미 존재하는 사용자 ID입니다.: " + userId);
    }
}
