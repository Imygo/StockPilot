import axios from 'axios';

// 1. 기본 Axios 인스턴스 생성
const apiClient = axios.create({
  // 환경변수가 없으면 기본 로컬 주소 사용
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080', 
  timeout: 5000,
  // 사용자 식별을 위한 세션 쿠키를 요청마다 포함하도록 설정[cite: 54]
  withCredentials: true, 
  headers: {
    'Content-Type': 'application/json',
  },
});

// 2. User API (UserController)
export const userAPI = {
  // 사용자 이름 등록
  registerUser: async (userName) => {
    const response = await apiClient.post('/api/users', { name: userName });
    return response.data;
  },
  // 사용자 존재 여부 확인
  checkUserExists: async (userId) => {
    const response = await apiClient.get('/api/users/exists', { params: { userId } });
    return response.data;
  }
};

// 3. Stock API (StockController)[cite: 52]
export const stockAPI = {
  // 주식 리스트 불러오기 (전체 또는 조건부 검색)
  getStocks: async ({ keyword, market, sort } = {}) => {
    // 프론트엔드 단에서 공백 문자열 검색 시도 1차 차단 (400 Bad Request 방지)[cite: 52]
    if (keyword !== undefined && keyword.trim() === '') {
      return Promise.reject(new Error('검색어는 공백일 수 없습니다.'));
    }
    const response = await apiClient.get('/api/stocks', { 
      params: { keyword, market, sort } 
    });
    return response.data;
  },
  // 주식 상세정보 조회
  getStockDetail: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}`);
    return response.data;
  }
};

// 4. Opinion API (OpinionController)[cite: 53]
export const opinionAPI = {
  // 커뮤니티 의견 집계 조회
  getCommunityOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/community-opinion`);
    return response.data;
  },
  // 유저 개인의 의견(투표) 등록
  postUserOpinion: async (stockCode, opinion) => {
    const response = await apiClient.post(`/api/stocks/${stockCode}/user-opinion`, { opinion });
    return response.data;
  }
};

// 5. Chart API (ChartController)[cite: 53]
export const chartAPI = {
  // 일봉 차트 데이터 조회 (날짜 형식: yyyy-MM-dd)[cite: 53, 54]
  getDailyChart: async (stockCode, startDate, endDate) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/daily-chart`, {
      params: { startDate, endDate }
    });
    return response.data;
  },
  // 분봉 차트 데이터 조회 (날짜 형식: yyyy-MM-ddTHH:mm:ss)[cite: 53, 54]
  getMinuteChart: async (stockCode, candleStart) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/minute-chart`, {
      params: { candleStart }
    });
    return response.data;
  },
  // 지표 차트 데이터 조회 (배열 파라미터 처리)[cite: 53, 54]
  getIndicatorChart: async (stockCode, startDate, endDate, technicalIndicators = []) => {
    const params = new URLSearchParams();
    if (startDate) params.append('startDate', startDate);
    if (endDate) params.append('endDate', endDate);
    
    // technicalIndicators=[RSI, SMA20] 배열을 technicalIndicators=RSI&technicalIndicators=SMA20 형태로 직렬화[cite: 53]
    technicalIndicators.forEach(indicator => {
      params.append('technicalIndicators', indicator);
    });

    const response = await apiClient.get(`/api/stocks/${stockCode}/indicator-chart`, { params });
    return response.data;
  }
};

// 6. AI Opinion API (AiOpinionController)[cite: 54]
export const aiOpinionAPI = {
  // 특정 주식의 AI 예측 결과 조회
  getAiOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/ai-opinion`);
    return response.data;
  }
};