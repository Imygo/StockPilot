import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { userAPI, getErrorMessage } from '../services/api';

export default function UserRegister() {
    const navigate = useNavigate();

    const [userId, setUserId] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

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
            navigate('/', { replace: true });
        } catch (error) {
            if (error.response?.status === 401) {
                sessionStorage.removeItem('stockpilot_user');
                setError('사용자 등록 후 세션을 확인하지 못했습니다. 브라우저의 쿠키 설정과 서버 상태를 확인해주세요.');
            } else if (error.response?.status === 409) {
                setError(
                    '이미 등록된 ID입니다. 현재는 신규 ID 등록만 지원합니다.'
                );
            } else {
                setError(getErrorMessage(error));
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <main>
            <h1>사용자 ID 등록</h1>
            <p>사용자 ID를 등록하면 주식 목록으로 이동합니다.</p>

            <form onSubmit={handleSubmit}>
                <label htmlFor="userId">사용자 ID</label>

                <input
                    id="userId"
                    value={userId}
                    onChange={(event) => setUserId(event.target.value)}
                    placeholder="새 사용자 ID 입력"
                    maxLength={50}
                    disabled={submitting}
                    required
                />

                <button type="submit" disabled={submitting}>
                    {submitting ? '등록 중...' : '등록'}
                </button>

                {error && <p role="alert">{error}</p>}
            </form>
        </main>
    );
}
