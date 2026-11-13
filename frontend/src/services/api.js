import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 10000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
  registerUser: async (userId) => {
    const trimmed = userId?.trim();
    if (!trimmed) {
      throw new Error('사용자 ID를 입력해주세요.');
    }
    const response = await apiClient.post('/api/users', { userId: trimmed });
    return response.data;
  },

  checkUserExists: async (userId) => {
    const response = await apiClient.get('/api/users/exists', {
      params: { userId: userId?.trim() },
    });
    return response.data;
  },
};

// 2. Stock API (StockController)
export const stockAPI = {
  getStocks: async ({ keyword, market, sort } = {}) => {
    const params = {};

    if (keyword !== undefined && keyword !== null) {
      if (keyword.trim() === '') {
        throw new Error('검색어를 입력해주세요.');
      }
      params.keyword = keyword.trim();
    }

    if (market && market !== 'ALL') {
      params.market = market;
    }

    if (sort) {
      params.sort = sort;
    }

    const response = await apiClient.get('/api/stocks', { params });
    return response.data;
  },

  getStockDetail: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}`);
    return response.data;
  },
};

// 3. Opinion API (OpinionController)
export const opinionAPI = {
  getCommunityOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/community-opinion`);
    return response.data;
  },

  // 새로 추가됨: 사용자가 제출한 의견 및 제출 시간 조회 (CheckOwnOpinionResponse)
  getOwnOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/own-opinion`);
    return response.data;
  },

  postUserOpinion: async (stockCode, opinion) => {
    const response = await apiClient.post(`/api/stocks/${stockCode}/user-opinion`, {
      opinion,
    });
    return response.data;
  },
};

// 4. Chart API (ChartController)
export const chartAPI = {
  getDailyChart: async (stockCode, startDate, endDate) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/daily-chart`, {
      params: { startDate, endDate },
    });
    return response.data;
  },

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
  getAiOpinion: async (stockCode) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/ai-opinion`);
    return response.data;
  },
};

// 6. Stock News API (StockNewsController)
export const newsAPI = {
  getStockNews: async (stockCode, limit = 30) => {
    const response = await apiClient.get(`/api/stocks/${stockCode}/news`, {
      params: { limit },
    });
    return response.data;
  },
};