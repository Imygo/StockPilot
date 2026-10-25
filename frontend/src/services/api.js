import axios from 'axios';

// Vite 프록시(http://localhost:5173/api)를 그대로 타도록 기본 baseURL은 빈 문자열로 설정합니다.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 10000,
  withCredentials: true, // 세션 쿠키(userId) 유지 필수
  headers: {
    'Content-Type': 'application/json',
  },
});

// 공통 에러 메시지 추출 헬퍼 함수
export const getErrorMessage = (error) => {
  if (error.response?.data?.message) {
    return error.response.data.message;
  }
  if (error.response?.status) {
    return `Request failed with status code ${error.response.status}`;
  }
  if (error.code === 'ERR_NETWORK') {
    return '서버에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.';
  }
  return error.message || '요청 처리 중 오류가 발생했습니다.';
};

// 1. User API (UserController)
export const userAPI = {
  // 사용자 등록: POST /api/users (본문: { userId }, 응답: 201 Created 빈 본문)
  registerUser: async (userId) => {
    const trimmed = userId?.trim();
    if (!trimmed) {
      throw new Error('사용자 ID를 입력해주세요.');
    }
    const response = await apiClient.post('/api/users', { userId: trimmed });
    return response.data;
  },

  // 사용자 존재 여부 확인: GET /api/users/exists?userId=user001 (응답: boolean)
  checkUserExists: async (userId) => {
    const response = await apiClient.get('/api/users/exists', {
      params: { userId: userId?.trim() },
    });
    return response.data;
  },
};

// 2. Stock API (StockController)
export const stockAPI = {
  // 주식 리스트 조회: GET /api/stocks
  getStocks: async ({ keyword, market, sort } = {}) => {
    const params = {};

    // keyword가 전달되었는데 빈 문자열/공백이면 400 Bad Request 대상이므로 차단
    if (keyword !== undefined && keyword !== null) {
      if (keyword.trim() === '') {
        throw new Error('검색어를 입력해주세요.');
      }
      params.keyword = keyword.trim();
    }

    // market이 ALL이거나 없으면 파라미터에서 생략 (백엔드에서 전체 조회 처리)
    if (market && market !== 'ALL') {
      params.market = market;
    }

    // 정렬 조건 전달 (예: VOLUME_DESC, SEARCH_PRIORITY 등)
    if (sort) {
      params.sort = sort;
    }

    const response = await apiClient.get('/api/stocks', { params });
    return response.data;
  },

  // 주식 상세정보 조회: GET /api/stocks/{stockCode}
  getStockDetail: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}`);
    return response.data;
  },
};

// 3. Opinion API (OpinionController)
export const opinionAPI = {
  // 커뮤니티 의견 조회: GET /api/stocks/{stockCode}/community-opinion
  getCommunityOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/community-opinion`);
    return response.data;
  },

  // 유저 의견 제출·변경: POST /api/stocks/{stockCode}/user-opinion (본문: { opinion: "BUY" | "SELL" })
  postUserOpinion: async (stockCode, opinion) => {
    const response = await apiClient.post(`/api/stocks/${stockCode}/user-opinion`, {
      opinion,
    });
    return response.data;
  },
};

// 4. Chart API (ChartController)
export const chartAPI = {
  // 일봉 차트 조회: GET /api/stocks/{stockCode}/daily-chart?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD
  getDailyChart: async (stockCode, startDate, endDate) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/daily-chart`, {
      params: { startDate, endDate },
    });
    return response.data;
  },

  // 분봉 차트 조회: GET /api/stocks/{stockCode}/minute-chart?candleStart=YYYY-MM-DDTHH:mm:ss
  getMinuteChart: async (stockCode, candleStart) => {
    const params = {};
    if (candleStart) {
      params.candleStart = candleStart;
    }
    const response = await apiClient.get(`/api/stocks/${stockCode}/minute-chart`, {
      params,
    });
    return response.data;
  },

  // 지표 차트 조회: GET /api/stocks/{stockCode}/indicator-chart?startDate=...&endDate=...&technicalIndicators=SMA20...
  getIndicatorChart: async (stockCode, startDate, endDate, technicalIndicators = []) => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);

    technicalIndicators.forEach((indicator) => {
      params.append('technicalIndicators', indicator);
    });

    const response = await apiClient.get(`/api/stocks/${stockCode}/indicator-chart`, {
      params,
    });
    return response.data;
  },
};

// 5. AI Opinion API (AiOpinionController)
export const aiOpinionAPI = {
  // AI 예측 결과 조회: GET /api/stocks/{stockCode}/ai-opinion
  getAiOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/ai-opinion`);
    return response.data;
  },
};