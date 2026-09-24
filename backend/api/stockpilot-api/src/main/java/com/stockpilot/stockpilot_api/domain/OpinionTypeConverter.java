package com.stockpilot.stockpilot_api.domain;

import com.stockpilot.stockpilot_api.global.enums.OpinionType;
import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;
import java.util.Locale;

@Converter
public class OpinionTypeConverter implements AttributeConverter<OpinionType, String> {
    // stockpilot_db.sql에서 enum값을 소문자로 지정했기 때문에, 변환하는 기능이 필요합니다.
    // sql 컬럼이 소문자이기도 하고 자바 프로젝트에선 대문자로 사용하기도 하니
    // 일단 추가해놓습니다
    @Override
    public String convertToDatabaseColumn(OpinionType opinion) {
        return opinion == null ? null : opinion.name().toLowerCase(Locale.ROOT);
    }

    @Override
    public OpinionType convertToEntityAttribute(String value) {
        return value == null ? null : OpinionType.valueOf(value.toUpperCase(Locale.ROOT));
    }
}
