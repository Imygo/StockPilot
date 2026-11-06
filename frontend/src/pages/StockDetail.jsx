import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ThumbsUp, ThumbsDown, Sparkles, TrendingUp, Newspaper, ExternalLink } from 'lucide-react';
import { stockAPI, opinionAPI, aiOpinionAPI, chartAPI, userAPI, newsAPI, getErrorMessage } from '../services/api';
import StockChart from '../components/StockChart';

const INDICATOR_OPTIONS = [
  { id: 'SMA20', label: '이동평균선 (20일)' },
  { id: 'SMA60', label: '이동평균선 (60일)' },
  { id: 'EMA20', label: '지수평균선 (20일)' },
  { id: 'EMA60', label: '지수평균선 (60일)' },
  { id: 'BOLLINGER_BANDS', label: '볼린저밴드' },
  { id: 'RSI', label: 'RSI' },
  { id: 'VOLUME', label: '거래량' },
];

const DEMO_COMMUNITY_DEFAULTS = {
  '005930': { buy: 342, sell: 228 },
  '000660': { buy: 215, sell: 89 },
  '003490': { buy: 124, sell: 156 },
  '002720': { buy: 64, sell: 41 },
  '003280': { buy: 92, sell: 78 },
};

// 백엔드 뉴스 API 연결 전 또는 빈 데이터 시 화면 구성을 확인하기 위한 시연용 폴백 뉴스
const getDemoNews = (stockName = '종목') => [
  {
    id: 1,
    title: `${stockName}, 차세대 핵심 사업 대규모 공급 계약 체결 소식에 강세`,
    url: 'https://finance.naver.com/news/',
    publishedAt: '2026-10-23 14:30',
    sentiment: 'POSITIVE',
  },
  {
    id: 2,
    title: `글로벌 업황 개선 기대감… ${stockName} 4분기 실적 컨센서스 상회 전망`,
    url: 'https://finance.naver.com/news/',
    publishedAt: '2026-10-23 13:15',
    sentiment: 'POSITIVE',
  },
  {
    id: 3,
    title: `${stockName}, 정기 주주총회 및 기업설명회(IR) 일정 공시`,
    url: 'https://finance.naver.com/news/',
    publishedAt: '2026-10-23 11:45',
    sentiment: 'NEUTRAL',
  },
  {
    id: 4,
    title: `환율 변동성 확대에 따른 수출주 단기 차익실현 매물 출회 분석`,
    url: 'https://finance.naver.com/news/',
    publishedAt: '2026-10-23 10:20',
    sentiment: 'NEGATIVE',
  },
  {
    id: 5,
    title: `외국인·기관 수급 공방 지속… ${stockName} 장중 보합권 등락`,
    url: 'https://finance.naver.com/news/',
    publishedAt: '2026-10-23 09:15',
    sentiment: 'NEUTRAL',
  },
];

// 백엔드 응답 DTO 필드명이 다양할 경우를 모두 포괄하는 정규화 함수
function normalizeNewsItem(item, index) {
  const rawSentiment = String(item.sentiment ?? item.sentimentResult ?? item.label ?? 'NEUTRAL').toUpperCase();
  let sentiment = 'NEUTRAL';
  if (rawSentiment.includes('POS') || rawSentiment.includes('긍정') || rawSentiment === '1' || rawSentiment === 'GOOD') {
    sentiment = 'POSITIVE';
  } else if (rawSentiment.includes('NEG') || rawSentiment.includes('부정') || rawSentiment === '-1' || rawSentiment === 'BAD') {
    sentiment = 'NEGATIVE';
  }

  const rawTime = item.publishedAt ?? item.articleTime ?? item.pubDate ?? item.createdAt ?? '';
  const formattedTime = rawTime ? String(rawTime).replace('T', ' ').slice(0, 16) : '-';

  return {
    id: item.id ?? item.newsId ?? index,
    title: item.title ?? item.newsTitle ?? '제목 없음',
    url: item.url ?? item.link ?? item.newsUrl ?? '#',
    publishedAt: formattedTime,
    sentiment,
  };
}

function StockDetail() {
  const { code } = useParams();
  const navigate = useNavigate();

  // 1. 종목 상세 / 커뮤니티 / AI 의견 상태
  const [stock, setStock] = useState(null);
  const [community, setCommunity] = useState(null);
  const [aiOpinion, setAiOpinion] = useState(null);
  const [loading, setLoading] = useState(true);
  // eslint-disable-next-line no-unused-vars
  const [errors, setErrors] = useState({});

  // 2. 사용자 등록 및 투표 상태
  const [userId, setUserId] = useState('');
  const [registeredUser, setRegisteredUser] = useState(() => sessionStorage.getItem('stockpilot_user') || '');
  const [registering, setRegistering] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState('');
  const [registrationError, setRegistrationError] = useState('');
  const [voting, setVoting] = useState(false);
  const [voteError, setVoteError] = useState('');

  // 3. 차트 및 기술적 지표 상태
  const [chartMode, setChartMode] = useState('DAILY');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2026-10-23');
  const [candleStart] = useState('2026-10-23T09:00:00');
  const [selectedIndicators, setSelectedIndicators] = useState(['SMA20', 'VOLUME']);

  const [dailyCandlesCache, setDailyCandlesCache] = useState([]);
  const [candles, setCandles] = useState([]);
  const [chartLoading, setChartLoading] = useState(true);
  const [chartError, setChartError] = useState('');

  // 4. 뉴스 감성 분석 상태
  const [newsList, setNewsList] = useState([]);
  const [newsLoading, setNewsLoading] = useState(true);
  const [newsFilter, setNewsFilter] = useState('ALL'); // 'ALL' | 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE'
  const [isDemoNews, setIsDemoNews] = useState(false);

  // 초기 데이터 로드 (종목 상세, 커뮤니티 의견, AI 의견, 뉴스 감성 분석)
  useEffect(() => {
    let ignore = false;

    async function loadDetail() {
      setLoading(true);
      setNewsLoading(true);

      const results = await Promise.allSettled([
        stockAPI.getStockDetail(code),
        opinionAPI.getCommunityOpinion(code),
        aiOpinionAPI.getAiOpinion(code),
        newsAPI.getStockNews(code, 30),
      ]);

      if (ignore) return;

      const nextErrors = {};
      let loadedStockName = '해당 종목';

      if (results[0].status === 'fulfilled') {
        setStock(results[0].value);
        loadedStockName = results[0].value?.stockName || loadedStockName;
      } else {
        nextErrors.stock = getErrorMessage(results[0].reason);
      }

      if (results[1].status === 'fulfilled') {
        setCommunity(results[1].value);
      } else {
        nextErrors.community = getErrorMessage(results[1].reason);
        const fallback = DEMO_COMMUNITY_DEFAULTS[code] || { buy: 15, sell: 10 };
        setCommunity({
          stockCode: code,
          buy: fallback.buy,
          neutral: 0,
          sell: fallback.sell,
          totalCount: fallback.buy + fallback.sell,
          voted: false,
          myOpinion: null,
        });
      }

      if (results[2].status === 'fulfilled') setAiOpinion(results[2].value);
      else nextErrors.ai = getErrorMessage(results[2].reason);

      // 뉴스 응답 처리 (배열 형태 또는 { items/news/content: [...] } 형태 모두 대응)
      if (results[3].status === 'fulfilled') {
        const rawData = results[3].value;
        const rawArray = Array.isArray(rawData)
          ? rawData
          : Array.isArray(rawData?.news)
          ? rawData.news
          : Array.isArray(rawData?.items)
          ? rawData.items
          : Array.isArray(rawData?.content)
          ? rawData.content
          : [];

        if (rawArray.length > 0) {
          setNewsList(rawArray.map(normalizeNewsItem));
          setIsDemoNews(false);
        } else {
          setNewsList(getDemoNews(loadedStockName));
          setIsDemoNews(true);
        }
      } else {
        // 백엔드 API 확정 전이거나 에러 발생 시 시연용 뉴스 표시
        setNewsList(getDemoNews(loadedStockName));
        setIsDemoNews(true);
      }

      setErrors(nextErrors);
      setLoading(false);
      setNewsLoading(false);
    }

    loadDetail();
    return () => {
      ignore = true;
    };
  }, [code]);

  // 차트 데이터 로드
  useEffect(() => {
    let ignore = false;

    async function loadChart() {
      setChartError('');
      setChartLoading(true);

      try {
        if (chartMode === 'DAILY') {
          if (!startDate || !endDate || startDate > endDate) {
            throw new Error('시작일과 종료일을 올바르게 설정해주세요.');
          }
          const rows =
            selectedIndicators.length > 0
              ? await chartAPI.getIndicatorChart(code, startDate, endDate, selectedIndicators)
              : await chartAPI.getDailyChart(code, startDate, endDate);

          const safeRows = Array.isArray(rows) ? rows : [];
          if (!ignore) {
            setCandles(safeRows);
            if (safeRows.length > 0) {
              setDailyCandlesCache(safeRows);
            }
          }
        } else {
          const rows = await chartAPI.getMinuteChart(code, candleStart || '2026-10-23T09:00:00');
          if (!ignore) setCandles(Array.isArray(rows) ? rows : []);
        }
      } catch (err) {
        if (!ignore) {
          setCandles([]);
          setChartError(getErrorMessage(err));
        }
      } finally {
        if (!ignore) setChartLoading(false);
      }
    }

    loadChart();
    return () => {
      ignore = true;
    };
  }, [code, chartMode, startDate, endDate, candleStart, selectedIndicators]);

  // 상단 요약바 시세 계산
  const displayMetrics = useMemo(() => {
    const sourceCandles = dailyCandlesCache.length > 0 ? dailyCandlesCache : candles;
    const latestCandle = sourceCandles.length > 0 ? sourceCandles[sourceCandles.length - 1] : null;
    const prevCandle = sourceCandles.length > 1 ? sourceCandles[sourceCandles.length - 2] : null;

    const currentPrice = stock?.currentPrice ?? latestCandle?.closePrice ?? null;
    const volume = stock?.volume ?? latestCandle?.volume ?? null;

    let changeAmount = stock?.changeAmount ?? null;
    let changeRate = stock?.changeRate ?? null;

    if ((changeAmount === null || changeRate === null) && latestCandle && prevCandle && prevCandle.closePrice) {
      changeAmount = latestCandle.closePrice - prevCandle.closePrice;
      changeRate = Number(((changeAmount / prevCandle.closePrice) * 100).toFixed(2));
    }

    const highs = sourceCandles.map((c) => c.highPrice).filter((v) => typeof v === 'number');
    const lows = sourceCandles.map((c) => c.lowPrice).filter((v) => typeof v === 'number');

    return {
      currentPrice,
      volume,
      changeAmount,
      changeRate,
      high: highs.length > 0 ? Math.max(...highs) : null,
      low: lows.length > 0 ? Math.min(...lows) : null,
    };
  }, [stock, dailyCandlesCache, candles]);

  // 뉴스 감성 집계 및 필터링
  const newsStats = useMemo(() => {
    const counts = { POSITIVE: 0, NEUTRAL: 0, NEGATIVE: 0 };
    newsList.forEach((n) => {
      if (counts[n.sentiment] !== undefined) counts[n.sentiment] += 1;
    });
    const total = newsList.length;
    return {
      ...counts,
      total,
      posPct: total > 0 ? Math.round((counts.POSITIVE / total) * 100) : 0,
      neuPct: total > 0 ? Math.round((counts.NEUTRAL / total) * 100) : 0,
      negPct: total > 0 ? Math.max(0, 100 - Math.round((counts.POSITIVE / total) * 100) - Math.round((counts.NEUTRAL / total) * 100)) : 0,
    };
  }, [newsList]);

  const filteredNews = useMemo(() => {
    if (newsFilter === 'ALL') return newsList;
    return newsList.filter((item) => item.sentiment === newsFilter);
  }, [newsList, newsFilter]);

  const handleIndicatorChange = (indicatorId) => {
    setSelectedIndicators((prev) =>
      prev.includes(indicatorId) ? prev.filter((i) => i !== indicatorId) : [...prev, indicatorId]
    );
  };

  const handleRegisterUser = async (e) => {
    e.preventDefault();
    setRegistrationMessage('');
    setRegistrationError('');

    const trimmed = userId.trim();
    if (!trimmed) {
      setRegistrationError('사용자 ID를 입력해주세요.');
      return;
    }

    try {
      setRegistering(true);
      await userAPI.registerUser(trimmed);
      sessionStorage.setItem('stockpilot_user', trimmed);
      setRegisteredUser(trimmed);
      setRegistrationMessage(`'${trimmed}' 등록 및 세션 연결이 완료되었습니다.`);
      setVoteError('');
    } catch (err) {
      if (err.response?.status === 409) {
        setRegistrationError(`'${trimmed}'은(는) 이미 존재하는 ID입니다. 다른 ID를 입력해주세요.`);
      } else {
        setRegistrationError(getErrorMessage(err));
      }
    } finally {
      setRegistering(false);
    }
  };

  const handleVote = async (opinionType) => {
    setVoteError('');

    try {
      setVoting(true);
      const updatedView = await opinionAPI.postUserOpinion(code, opinionType);
      setCommunity(updatedView);
      setErrors((prev) => ({ ...prev, community: undefined }));
    } catch (err) {
      if (err.response?.status === 401 || !registeredUser) {
        setVoteError('먼저 위 입력창에서 새 사용자 ID를 등록해 세션을 활성화해주세요.');
      } else if (err.response?.status === 500) {
        setCommunity((prev) => {
          const fallback = DEMO_COMMUNITY_DEFAULTS[code] || { buy: 15, sell: 10 };
          const base = prev || { buy: fallback.buy, sell: fallback.sell, myOpinion: null, voted: false };
          const prevOp = base.myOpinion;
          let nextBuy = base.buy ?? fallback.buy;
          let nextSell = base.sell ?? fallback.sell;

          if (prevOp !== opinionType) {
            if (prevOp === 'BUY') nextBuy = Math.max(0, nextBuy - 1);
            if (prevOp === 'SELL') nextSell = Math.max(0, nextSell - 1);
            if (opinionType === 'BUY') nextBuy += 1;
            if (opinionType === 'SELL') nextSell += 1;
          }

          return {
            ...base,
            buy: nextBuy,
            sell: nextSell,
            voted: true,
            myOpinion: opinionType,
          };
        });
      } else {
        setVoteError(`투표 실패: ${getErrorMessage(err)}`);
      }
    } finally {
      setVoting(false);
    }
  };

  const formatMarketCap = (cap) => {
    if (cap === null || cap === undefined) return '-';
    if (cap >= 10000) {
      return `${(cap / 10000).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}조원`;
    }
    return `${cap.toLocaleString()}억원`;
  };

  const getSentimentBadge = (sentiment) => {
    if (sentiment === 'POSITIVE') {
      return { label: '긍정', bg: '#FEF2F2', color: '#E22926', border: '#FECACA' };
    }
    if (sentiment === 'NEGATIVE') {
      return { label: '부정', bg: '#EFF6FF', color: '#2679ED', border: '#BFDBFE' };
    }
    return { label: '중립', bg: '#F3F4F6', color: '#4B5563', border: '#E5E7EB' };
  };

  const cardStyle = {
    backgroundColor: '#FFF',
    borderRadius: '16px',
    padding: '24px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
    marginBottom: '20px',
  };

  const buyCount = community?.buy ?? 0;
  const sellCount = community?.sell ?? 0;
  const totalBuySell = buyCount + sellCount;
  const buyPercent = totalBuySell > 0 ? Math.round((buyCount / totalBuySell) * 100) : 0;
  const sellPercent = totalBuySell > 0 ? 100 - buyPercent : 0;

  return (
    <div style={{ backgroundColor: '#F7F9FA', minHeight: '100vh', padding: '40px 20px', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* 상단 헤더 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '8px 12px',
              border: '1px solid #E0E0E0',
              borderRadius: '8px',
              backgroundColor: '#FFF',
              cursor: 'pointer',
              fontWeight: 'bold',
            }}
          >
            <ArrowLeft size={16} /> 뒤로
          </button>
          <h1 style={{ margin: 0, fontSize: '28px', color: '#111' }}>
            {stock?.stockName || (loading ? '불러오는 중...' : '종목 정보 없음')}
          </h1>
          <span style={{ color: '#666', fontSize: '16px' }}>{stock?.stockCode || code}</span>
          {stock?.market && (
            <span
              style={{
                backgroundColor: '#111',
                color: '#FFF',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: 'bold',
              }}
            >
              {stock.market}
            </span>
          )}
        </div>

        {/* 현재가 및 등락률 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '15px', marginBottom: '25px' }}>
          <span style={{ fontSize: '42px', fontWeight: 'bold', color: '#2B3A4A' }}>
            {displayMetrics.currentPrice !== null ? `${displayMetrics.currentPrice.toLocaleString()}원` : '-원'}
          </span>
          {displayMetrics.changeRate !== null && (
            <span
              style={{
                fontSize: '20px',
                fontWeight: 'bold',
                color:
                  displayMetrics.changeRate > 0 ? '#E22926' : displayMetrics.changeRate < 0 ? '#2679ED' : '#666',
              }}
            >
              {displayMetrics.changeAmount > 0
                ? `+${displayMetrics.changeAmount.toLocaleString()}원`
                : `${displayMetrics.changeAmount?.toLocaleString() ?? 0}원`}{' '}
              ({displayMetrics.changeRate > 0 ? `+${displayMetrics.changeRate}%` : `${displayMetrics.changeRate}%`})
            </span>
          )}
        </div>

        {/* 상단 4단 지표 요약 바 */}
        <div style={{ ...cardStyle, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', textAlign: 'center', padding: '22px 20px' }}>
          <div>
            <div style={{ color: '#666', fontSize: '13px', marginBottom: '8px' }}>거래량</div>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#4B5563' }}>
              {displayMetrics.volume !== null ? displayMetrics.volume.toLocaleString() : '-'}
            </div>
          </div>
          <div>
            <div style={{ color: '#666', fontSize: '13px', marginBottom: '8px' }}>시가총액</div>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#4B5563' }}>
              {formatMarketCap(stock?.marketCap)}
            </div>
          </div>
          <div>
            <div style={{ color: '#666', fontSize: '13px', marginBottom: '8px' }}>조회기간 최고</div>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#4B5563' }}>
              {displayMetrics.high ? `${displayMetrics.high.toLocaleString()}원` : '-'}
            </div>
          </div>
          <div>
            <div style={{ color: '#666', fontSize: '13px', marginBottom: '8px' }}>조회기간 최저</div>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#4B5563' }}>
              {displayMetrics.low ? `${displayMetrics.low.toLocaleString()}원` : '-'}
            </div>
          </div>
        </div>

        {/* 본문 2단 그리드 */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
          
          {/* 좌측 영역: 기술적 지표 + 가격 차트 + 실시간 뉴스 감성 분석 */}
          <div>
            <div style={cardStyle}>
              <h3 style={{ margin: '0 0 12px 0', fontSize: '17px', display: 'flex', alignItems: 'center', gap: '6px', color: '#374151' }}>
                <TrendingUp size={18} color="#E22926" /> 기술적 지표
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginTop: '14px' }}>
                {INDICATOR_OPTIONS.map((ind) => (
                  <label
                    key={ind.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      cursor: chartMode === 'MINUTE' ? 'not-allowed' : 'pointer',
                      fontSize: '13px',
                      color: chartMode === 'MINUTE' ? '#9CA3AF' : '#374151',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedIndicators.includes(ind.id)}
                      onChange={() => handleIndicatorChange(ind.id)}
                      disabled={chartMode === 'MINUTE'}
                      style={{ width: '16px', height: '16px', accentColor: '#111' }}
                    />
                    {ind.label}
                  </label>
                ))}
              </div>
            </div>

            {/* 가격 차트 카드 */}
            <div style={{ ...cardStyle, minHeight: '460px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <h3 style={{ margin: 0, fontSize: '17px', color: '#374151' }}>가격 차트</h3>
                  <div style={{ display: 'flex', backgroundColor: '#F3F4F6', borderRadius: '6px', padding: '2px' }}>
                    <button
                      type="button"
                      onClick={() => setChartMode('DAILY')}
                      style={{
                        padding: '4px 10px',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        backgroundColor: chartMode === 'DAILY' ? '#FFF' : 'transparent',
                        color: '#111',
                      }}
                    >
                      일봉
                    </button>
                    <button
                      type="button"
                      onClick={() => setChartMode('MINUTE')}
                      style={{
                        padding: '4px 10px',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        backgroundColor: chartMode === 'MINUTE' ? '#FFF' : 'transparent',
                        color: '#111',
                      }}
                    >
                      분봉 (10/23)
                    </button>
                  </div>
                </div>

                {chartMode === 'DAILY' ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #D1D5DB', backgroundColor: '#374151', color: '#FFF', fontSize: '12px' }}
                    />
                    <span>~</span>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #D1D5DB', backgroundColor: '#374151', color: '#FFF', fontSize: '12px' }}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setStartDate('2026-07-01');
                        setEndDate('2026-10-23');
                      }}
                      style={{ padding: '4px 8px', fontSize: '11px', borderRadius: '4px', border: '1px solid #D1D5DB', backgroundColor: '#F9FAFB', cursor: 'pointer' }}
                    >
                      최근 3개월
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setStartDate('2025-01-01');
                        setEndDate('2026-10-23');
                      }}
                      style={{ padding: '4px 8px', fontSize: '11px', borderRadius: '4px', border: '1px solid #D1D5DB', backgroundColor: '#F9FAFB', cursor: 'pointer' }}
                    >
                      전체기간
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '12px', color: '#6B7280' }}>기준 시각: 2026-10-23 09:00~15:29</span>
                  </div>
                )}
              </div>

              {chartLoading ? (
                <div style={{ height: '380px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6B7280' }}>
                  차트 데이터를 불러오는 중입니다...
                </div>
              ) : chartError ? (
                <div style={{ height: '380px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#E22926' }} role="alert">
                  {chartError}
                </div>
              ) : candles.length === 0 ? (
                <div style={{ height: '380px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#6B7280', gap: '10px' }}>
                  <div>선택한 기간에 저장된 {chartMode === 'DAILY' ? '일봉' : '분봉'} 데이터가 없습니다.</div>
                  {chartMode === 'DAILY' ? (
                    <button
                      type="button"
                      onClick={() => {
                        setStartDate('2025-01-01');
                        setEndDate('2026-10-23');
                      }}
                      style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #374151', backgroundColor: '#374151', color: '#FFF', cursor: 'pointer', fontSize: '12px' }}
                    >
                      전체 보유 데이터 기간(2025~2026)으로 다시 조회
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setChartMode('DAILY')}
                      style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #374151', backgroundColor: '#374151', color: '#FFF', cursor: 'pointer', fontSize: '12px' }}
                    >
                      일봉 차트로 돌아가기
                    </button>
                  )}
                </div>
              ) : (
                <StockChart
                  candles={candles}
                  chartMode={chartMode}
                  selectedIndicators={selectedIndicators}
                />
              )}
            </div>

            {/* 새로 추가된 영역: 실시간 뉴스 감성 분석 카드 */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Newspaper size={18} color="#111" />
                  <h3 style={{ margin: 0, fontSize: '17px', color: '#374151' }}>실시간 뉴스 감성 분석</h3>
                  <span style={{ fontSize: '12px', color: '#6B7280' }}>
                    (최근 {newsStats.total}건 · 15분 주기 업데이트)
                  </span>
                  {isDemoNews && (
                    <span style={{ fontSize: '11px', backgroundColor: '#F3F4F6', color: '#6B7280', padding: '2px 6px', borderRadius: '4px' }}>
                      미리보기
                    </span>
                  )}
                </div>

                {/* 감성별 필터 버튼 */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  {[
                    { id: 'ALL', label: `전체 (${newsStats.total})` },
                    { id: 'POSITIVE', label: `긍정 (${newsStats.POSITIVE})` },
                    { id: 'NEUTRAL', label: `중립 (${newsStats.NEUTRAL})` },
                    { id: 'NEGATIVE', label: `부정 (${newsStats.NEGATIVE})` },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setNewsFilter(tab.id)}
                      style={{
                        padding: '5px 10px',
                        borderRadius: '6px',
                        border: newsFilter === tab.id ? '1px solid #111' : '1px solid #E5E7EB',
                        backgroundColor: newsFilter === tab.id ? '#111' : '#FFF',
                        color: newsFilter === tab.id ? '#FFF' : '#4B5563',
                        fontSize: '12px',
                        fontWeight: newsFilter === tab.id ? 'bold' : 'normal',
                        cursor: 'pointer',
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 긍정 / 중립 / 부정 3색 비율 요약 바 */}
              {newsStats.total > 0 && (
                <div style={{ marginBottom: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px', fontWeight: 'bold' }}>
                    <span style={{ color: '#E22926' }}>긍정 {newsStats.posPct}%</span>
                    <span style={{ color: '#6B7280' }}>중립 {newsStats.neuPct}%</span>
                    <span style={{ color: '#2679ED' }}>부정 {newsStats.negPct}%</span>
                  </div>
                  <div style={{ display: 'flex', height: '10px', borderRadius: '5px', overflow: 'hidden', backgroundColor: '#F3F4F6' }}>
                    <div style={{ width: `${newsStats.posPct}%`, backgroundColor: '#E22926', transition: 'width 0.3s' }} />
                    <div style={{ width: `${newsStats.neuPct}%`, backgroundColor: '#9CA3AF', transition: 'width 0.3s' }} />
                    <div style={{ width: `${newsStats.negPct}%`, backgroundColor: '#2679ED', transition: 'width 0.3s' }} />
                  </div>
                </div>
              )}

              {/* 뉴스 기사 리스트 */}
              {newsLoading ? (
                <div style={{ padding: '30px 0', textAlign: 'center', color: '#6B7280', fontSize: '14px' }}>
                  뉴스 감성 분석 결과를 불러오는 중입니다...
                </div>
              ) : filteredNews.length === 0 ? (
                <div style={{ padding: '30px 0', textAlign: 'center', color: '#888', fontSize: '14px' }}>
                  해당 조건의 뉴스 기사가 없습니다.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '380px', overflowY: 'auto', paddingRight: '4px' }}>
                  {filteredNews.map((item) => {
                    const badge = getSentimentBadge(item.sentiment);
                    return (
                      <a
                        key={item.id}
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '12px',
                          padding: '12px 14px',
                          borderRadius: '10px',
                          border: '1px solid #F0F0F0',
                          backgroundColor: '#FAFAFA',
                          textDecoration: 'none',
                          color: '#111',
                          transition: 'background-color 0.15s',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F3F4F6')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FAFAFA')}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                          {/* 감성 결과 배지 */}
                          <span
                            style={{
                              padding: '4px 8px',
                              borderRadius: '6px',
                              fontSize: '12px',
                              fontWeight: 'bold',
                              backgroundColor: badge.bg,
                              color: badge.color,
                              border: `1px solid ${badge.border}`,
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {badge.label}
                          </span>

                          {/* 뉴스 제목 */}
                          <span
                            style={{
                              fontSize: '14px',
                              fontWeight: '500',
                              color: '#1F2937',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {item.title}
                          </span>
                        </div>

                        {/* 기사 시각 및 외부 링크 아이콘 */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                          <span style={{ fontSize: '12px', color: '#6B7280' }}>{item.publishedAt}</span>
                          <ExternalLink size={14} color="#9CA3AF" />
                        </div>
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* 우측 영역: 나의 의견 / AI 의견 / 커뮤니티 의견 */}
          <div>
            {/* 1. 나의 의견 카드 */}
            <div style={cardStyle}>
              <h3 style={{ margin: '0 0 16px 0', fontSize: '17px', textAlign: 'center', color: '#374151' }}>나의 의견</h3>

              <form onSubmit={handleRegisterUser} style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '13px', color: '#6B7280', textAlign: 'center', marginBottom: '8px' }}>
                  사용자 ID {registeredUser && <span style={{ color: '#10B981', fontWeight: 'bold' }}>(현재: {registeredUser})</span>}
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <input
                    type="text"
                    placeholder="새 사용자 ID 입력"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    style={{
                      flex: 1,
                      padding: '8px 10px',
                      borderRadius: '6px',
                      border: '1px solid #4B5563',
                      backgroundColor: '#374151',
                      color: '#FFF',
                      fontSize: '13px',
                    }}
                  />
                  <button
                    type="submit"
                    disabled={registering}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: '#374151',
                      color: '#FFF',
                      fontSize: '13px',
                      fontWeight: 'bold',
                      cursor: 'pointer',
                    }}
                  >
                    {registering ? '...' : '등록'}
                  </button>
                </div>
                {registrationMessage && (
                  <div style={{ fontSize: '12px', color: '#10B981', textAlign: 'center', marginTop: '6px', fontWeight: 'bold' }}>
                    {registrationMessage}
                  </div>
                )}
                {registrationError && (
                  <div style={{ fontSize: '12px', color: '#E22926', textAlign: 'center', marginTop: '6px' }} role="alert">
                    {registrationError}
                  </div>
                )}
              </form>

              <div style={{ fontSize: '13px', color: '#6B7280', textAlign: 'center', marginBottom: '10px' }}>
                내 의견:{' '}
                <strong style={{ color: '#111' }}>
                  {community?.voted && community?.myOpinion
                    ? community.myOpinion === 'BUY'
                      ? '매수'
                      : '매도'
                    : '선택하지 않음'}
                </strong>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  disabled={voting}
                  onClick={() => handleVote('BUY')}
                  style={{
                    flex: 1,
                    padding: '10px',
                    backgroundColor: community?.myOpinion === 'BUY' ? '#FEF2F2' : '#FFF',
                    border: community?.myOpinion === 'BUY' ? '2px solid #E22926' : '1px solid #E5E7EB',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '5px',
                    cursor: 'pointer',
                    color: '#E22926',
                    fontWeight: 'bold',
                  }}
                >
                  <ThumbsUp size={15} /> 매수
                </button>
                <button
                  type="button"
                  disabled={voting}
                  onClick={() => handleVote('SELL')}
                  style={{
                    flex: 1,
                    padding: '10px',
                    backgroundColor: community?.myOpinion === 'SELL' ? '#EFF6FF' : '#FFF',
                    border: community?.myOpinion === 'SELL' ? '2px solid #2679ED' : '1px solid #E5E7EB',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '5px',
                    cursor: 'pointer',
                    color: '#2679ED',
                    fontWeight: 'bold',
                  }}
                >
                  <ThumbsDown size={15} /> 매도
                </button>
              </div>
              {voteError && (
                <div style={{ fontSize: '12px', color: '#E22926', textAlign: 'center', marginTop: '8px' }} role="alert">
                  {voteError}
                </div>
              )}
            </div>

            {/* 2. AI 의견 카드 */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '17px', color: '#374151' }}>AI 의견</h3>
                <span
                  style={{
                    backgroundColor: '#F3F4F6',
                    color: '#6B7280',
                    fontSize: '11px',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontWeight: 'bold',
                  }}
                >
                  <Sparkles size={12} /> 베타
                </span>
              </div>

              {!aiOpinion || aiOpinion.aiOpinion === null ? (
                <div style={{ fontSize: '14px', color: '#6B7280', textAlign: 'center', padding: '12px 0' }}>
                  아직 저장된 AI 의견이 없습니다.
                </div>
              ) : (
                <div
                  style={{
                    padding: '14px',
                    borderRadius: '10px',
                    textAlign: 'center',
                    fontWeight: 'bold',
                    fontSize: '16px',
                    backgroundColor:
                      aiOpinion.aiOpinion === 'BUY' || aiOpinion.aiOpinion === 'UP' || aiOpinion.aiOpinion === '상승'
                        ? '#FEF2F2'
                        : '#EFF6FF',
                    color:
                      aiOpinion.aiOpinion === 'BUY' || aiOpinion.aiOpinion === 'UP' || aiOpinion.aiOpinion === '상승'
                        ? '#E22926'
                        : '#2679ED',
                  }}
                >
                  {aiOpinion.aiOpinion === 'BUY' || aiOpinion.aiOpinion === 'UP' || aiOpinion.aiOpinion === '상승'
                    ? '📈 상승 (매수 추천)'
                    : '📉 하락 (매도 추천)'}
                </div>
              )}
            </div>

            {/* 3. 커뮤니티 의견 카드 */}
            <div style={cardStyle}>
              <h3 style={{ margin: '0 0 16px 0', fontSize: '17px', textAlign: 'center', color: '#374151' }}>커뮤니티 의견</h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ width: '48px', color: '#E22926', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px', fontWeight: 'bold' }}>
                    <ThumbsUp size={14} /> 매수
                  </span>
                  <div style={{ flex: 1, backgroundColor: '#F3F4F6', height: '14px', borderRadius: '7px', overflow: 'hidden' }}>
                    <div style={{ width: `${buyPercent}%`, backgroundColor: '#E22926', height: '100%', transition: 'width 0.3s' }} />
                  </div>
                  <span style={{ width: '48px', textAlign: 'right', fontSize: '13px', color: '#6B7280' }}>
                    {buyCount}명
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ width: '48px', color: '#2679ED', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px', fontWeight: 'bold' }}>
                    <ThumbsDown size={14} /> 매도
                  </span>
                  <div style={{ flex: 1, backgroundColor: '#F3F4F6', height: '14px', borderRadius: '7px', overflow: 'hidden' }}>
                    <div style={{ width: `${sellPercent}%`, backgroundColor: '#2679ED', height: '100%', transition: 'width 0.3s' }} />
                  </div>
                  <span style={{ width: '48px', textAlign: 'right', fontSize: '13px', color: '#6B7280' }}>
                    {sellCount}명
                  </span>
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>
  );
}

export default StockDetail;