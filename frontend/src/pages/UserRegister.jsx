import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { User } from 'lucide-react';
import { userAPI, getErrorMessage } from '../services/api';

function GoogleIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
            <path
                fill="#4285F4"
                d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
            />
            <path
                fill="#34A853"
                d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
            />
            <path
                fill="#FBBC05"
                d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"
            />
            <path
                fill="#EA4335"
                d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09c.95-2.85 3.6-4.96 6.73-4.96z"
            />
        </svg>
    );
}

export default function UserRegister() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    const [userId, setUserId] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');
    const [inputFocused, setInputFocused] = useState(false);

    const handleSubmit = async (event) => {
        event.preventDefault();

        if (submitting) return;

        const trimmed = userId.trim();
        setError('');

        if (!trimmed) {
            setError('사용자 ID를 입력해주세요.');
            return;
        }

        setSubmitting(true);

        try {
            await userAPI.registerUser(trimmed);

            // 등록 응답뿐 아니라 이후 요청에서도 세션이 유지되는지 확인합니다.
            const currentUser = await userAPI.getCurrentUser();
            if (!currentUser?.userId) {
                throw new Error('서버에서 사용자 세션을 확인하지 못했습니다.');
            }

            sessionStorage.setItem('stockpilot_user', currentUser.userId);
            sessionStorage.setItem(
                'stockpilot_display_name',
                currentUser.displayName ?? currentUser.userId
            );

            navigate('/', { replace: true });
        } catch (err) {
            if (err.response?.status === 401) {
                sessionStorage.removeItem('stockpilot_user');
                sessionStorage.removeItem('stockpilot_display_name');
                setError('사용자 등록 후 세션을 확인하지 못했습니다. 브라우저의 쿠키 설정과 서버 상태를 확인해주세요.');
            } else {
                setError(getErrorMessage(err));
            }
        } finally {
            setSubmitting(false);
        }
    };

    const googleLoginFailed = searchParams.get('error') === 'google';

    return (
        <main
            style={{
                minHeight: '100vh',
                width: '100%',
                backgroundColor: '#F3F5F8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '32px 16px',
                boxSizing: 'border-box',
                fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
            }}
        >
            <section
                style={{
                    width: '100%',
                    maxWidth: '420px',
                    backgroundColor: '#FFFFFF',
                    borderRadius: '20px',
                    border: '1px solid #E5EAF0',
                    boxShadow: '0 10px 30px rgba(15, 23, 42, 0.06)',
                    padding: '44px 36px 40px',
                    boxSizing: 'border-box',
                    textAlign: 'center',
                }}
            >
                {/* 로고 및 서비스명 */}
                <div style={{ marginBottom: '28px' }}>
                    <img
                        src="/stockpilot-logo.png"
                        alt="StockPilot 로고"
                        style={{
                            width: '84px',
                            height: '84px',
                            objectFit: 'contain',
                            display: 'block',
                            margin: '0 auto 10px',
                        }}
                    />
                    <div
                        style={{
                            fontSize: '30px',
                            fontWeight: '800',
                            letterSpacing: '-0.6px',
                            lineHeight: 1.2,
                            marginBottom: '10px',
                        }}
                    >
                        <span style={{ color: '#111827' }}>Stock</span>
                        <span style={{ color: '#65B741' }}>Pilot</span>
                    </div>
                    <p
                        style={{
                            margin: 0,
                            fontSize: '14px',
                            color: '#4B5563',
                            lineHeight: 1.5,
                        }}
                    >
                        AI 기반 주식 분석 및 투자 의견 플랫폼
                    </p>
                </div>

                {/* 입장 안내 제목 */}
                <div style={{ marginBottom: '26px' }}>
                    <h1
                        style={{
                            margin: '0 0 8px 0',
                            fontSize: '23px',
                            fontWeight: '700',
                            color: '#111827',
                            letterSpacing: '-0.3px',
                        }}
                    >
                        사용자 입장
                    </h1>
                    <p
                        style={{
                            margin: 0,
                            fontSize: '14px',
                            color: '#6B7280',
                            lineHeight: 1.5,
                        }}
                    >
                        StockPilot과 함께 시장의 흐름을 분석해 보세요.
                    </p>
                </div>

                {/* 로컬 사용자 ID 입장 폼 */}
                <form onSubmit={handleSubmit} style={{ textAlign: 'left' }}>
                    <label
                        htmlFor="userId"
                        style={{
                            display: 'block',
                            fontSize: '14px',
                            fontWeight: '600',
                            color: '#374151',
                            marginBottom: '8px',
                        }}
                    >
                        사용자 ID
                    </label>

                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            border: inputFocused ? '1.5px solid #313C4E' : '1px solid #D1D5DB',
                            borderRadius: '10px',
                            padding: '0 14px',
                            backgroundColor: submitting ? '#F9FAFB' : '#FFFFFF',
                            transition: 'border-color 0.15s ease',
                            marginBottom: '14px',
                            boxSizing: 'border-box',
                        }}
                    >
                        <User size={18} color="#9CA3AF" style={{ flexShrink: 0 }} />
                        <input
                            id="userId"
                            type="text"
                            value={userId}
                            onChange={(event) => setUserId(event.target.value)}
                            onFocus={() => setInputFocused(true)}
                            onBlur={() => setInputFocused(false)}
                            placeholder="사용자명을 입력하세요"
                            maxLength={50}
                            disabled={submitting}
                            required
                            autoComplete="username"
                            style={{
                                width: '100%',
                                border: 'none',
                                outline: 'none',
                                backgroundColor: 'transparent',
                                padding: '13px 0',
                                fontSize: '15px',
                                color: '#111827',
                                boxSizing: 'border-box',
                            }}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={submitting}
                        style={{
                            width: '100%',
                            padding: '14px 16px',
                            border: 'none',
                            borderRadius: '10px',
                            backgroundColor: submitting ? '#64748B' : '#313C4E',
                            color: '#FFFFFF',
                            fontSize: '16px',
                            fontWeight: '600',
                            cursor: submitting ? 'not-allowed' : 'pointer',
                            transition: 'background-color 0.15s ease',
                        }}
                    >
                        {submitting ? '입장 중...' : '입장하기'}
                    </button>

                    <p
                        style={{
                            margin: '12px 0 0 0',
                            fontSize: '13px',
                            color: '#6B7280',
                            textAlign: 'center',
                        }}
                    >
                        새로운 사용자명으로도 바로 입장할 수 있습니다.
                    </p>

                    {error && (
                        <p
                            role="alert"
                            style={{
                                margin: '14px 0 0 0',
                                padding: '10px 12px',
                                borderRadius: '8px',
                                backgroundColor: '#FEF2F2',
                                border: '1px solid #FECACA',
                                color: '#DC2626',
                                fontSize: '13px',
                                textAlign: 'center',
                                lineHeight: 1.4,
                            }}
                        >
                            {error}
                        </p>
                    )}
                </form>

                {/* 구분선 */}
                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        margin: '24px 0',
                    }}
                >
                    <div style={{ flex: 1, height: '1px', backgroundColor: '#E5E7EB' }} />
                    <span style={{ fontSize: '13px', color: '#6B7280' }}>또는</span>
                    <div style={{ flex: 1, height: '1px', backgroundColor: '#E5E7EB' }} />
                </div>

                {/* Google 로그인 버튼 */}
                <button
                    type="button"
                    disabled={submitting}
                    onClick={userAPI.loginWithGoogle}
                    style={{
                        width: '100%',
                        padding: '13px 16px',
                        borderRadius: '10px',
                        border: '1px solid #D1D5DB',
                        backgroundColor: '#FFFFFF',
                        color: '#374151',
                        fontSize: '15px',
                        fontWeight: '500',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '10px',
                        cursor: submitting ? 'not-allowed' : 'pointer',
                        transition: 'background-color 0.15s ease',
                    }}
                >
                    <GoogleIcon />
                    <span>Google 계정으로 로그인</span>
                </button>

                {googleLoginFailed && (
                    <p
                        role="alert"
                        style={{
                            margin: '14px 0 0 0',
                            padding: '10px 12px',
                            borderRadius: '8px',
                            backgroundColor: '#FEF2F2',
                            border: '1px solid #FECACA',
                            color: '#DC2626',
                            fontSize: '13px',
                            textAlign: 'center',
                            lineHeight: 1.4,
                        }}
                    >
                        Google 로그인에 실패했습니다. 다시 시도해주세요.
                    </p>
                )}
            </section>
        </main>
    );
}