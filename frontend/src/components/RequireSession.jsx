import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { userAPI, getErrorMessage } from '../services/api';

export default function RequireSession() {
    const location = useLocation();
    const [result, setResult] = useState({
        checkedPath: null,
        status: 'loading',
        message: '',
    });
    const [retryCount, setRetryCount] = useState(0);

    useEffect(() => {
        let ignore = false;
        const checkedPath = location.pathname;

        async function checkSession() {
            try {
                const user = await userAPI.getCurrentUser();

                if (ignore) return;

                // 서버가 확인한 ID로 기존 상세 화면의 표시값 동기화
                sessionStorage.setItem('stockpilot_user', user.userId);

                setResult({
                    checkedPath,
                    status: 'authenticated',
                    message: '',
                });
            } catch (error) {
                if (ignore) return;

                if (error.response?.status === 401) {
                    sessionStorage.removeItem('stockpilot_user');

                    setResult({
                        checkedPath,
                        status: 'unauthenticated',
                        message: '',
                    });
                } else {
                    // 서버 연결 실패를 세션 없음으로 취급하지 않음
                    setResult({
                        checkedPath,
                        status: 'error',
                        message: getErrorMessage(error),
                    });
                }
            }
        }

        checkSession();

        return () => {
            ignore = true;
        };
    }, [location.pathname, retryCount]);

    // 경로가 바뀌면 해당 경로의 세션 확인이 끝날 때까지 대기
    if (
        result.checkedPath !== location.pathname ||
        result.status === 'loading'
    ) {
        return <p role="status">사용자 세션을 확인하고 있습니다...</p>;
    }

    if (result.status === 'unauthenticated') {
        return <Navigate to="/register" replace />;
    }

    if (result.status === 'error') {
        return (
            <div role="alert">
                <p>세션을 확인하지 못했습니다.</p>
                <p>{result.message}</p>

                <button
                    type="button"
                    onClick={() => {
                        setResult({
                            checkedPath: null,
                            status: 'loading',
                            message: '',
                        });
                        setRetryCount((count) => count + 1);
                    }}
                >
                    다시 시도
                </button>
            </div>
        );
    }

    return <Outlet />;
}