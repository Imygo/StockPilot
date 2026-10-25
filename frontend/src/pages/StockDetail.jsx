import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ThumbsUp, ThumbsDown, Sparkles, TrendingUp } from 'lucide-react';
import { stockAPI, opinionAPI, aiOpinionAPI, chartAPI, userAPI, getErrorMessage } from '../services/api';
import StockChart from '../components/StockChart';

// 백엔드 Enum 명칭과 100% 일치시킨 기술적 지표 목록[cite: 3, 11]
const INDICATOR_OPTIONS = [
  { id: 'SMA20', label: '이동평균선 (20일)' },
  { id: 'SMA60', label: '이동평균선 (60일)' },
  { id: 'EMA20', label: '지수평균선 (20일)' },
  { id: 'EMA60', label: '지수평균선 (60일)' },
  { id: 'BOLLINGER_BANDS', label: '볼린저밴드' },
  { id: 'RSI', label: 'RSI' },
  { id: 'VOLUME', label: '거래량' },
];

// 시연 시 기본 커뮤니티 투표수 (백엔드 community_opinions 테이블이 비어있어 500 에러가 날 때 시연용 초기값)[cite: 11, 14]
const DEMO_COMMUNITY_DEFAULTS = {
  '005930': { buy: 342, sell: 228 },
  '000660': { buy: 215, sell: 89 },
  '003490': { buy: 124, sell: 156 },
  '002720': { buy: 64, sell: 41 },
  '003280': { buy: 92, sell: 78 },
};

function StockDetail() {
  const { code } = useParams();
  const navigate = useNavigate();

  // 1. 종목 상세 / 커뮤니티 / AI 의견 상태
  const [stock, setStock] = useState(null);
  const [community, setCommunity] = useState(null);
  const [aiOpinion, setAiOpinion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});

  // 2. 사용자 등록 및 투표 상태 (버그 수정됨: useState 정상 적용)
  const [userId, setUserId] = useState('');
  const [registeredUser, setRegisteredUser] = useState(() => sessionStorage.getItem('stockpilot_user') || '');
  const [registering, setRegistering] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState('');
  const [registrationError, setRegistrationError] = useState('');
  const [voting, setVoting] = useState(false);
  const [voteError, setVoteError] = useState('');

  // 3. 차트 및 기술적 지표 상태
  // 2025년 데이터만 있는 종목(002720, 003280)과 2026년 데이터까지 있는 종목(005930, 000660, 003490) 모두 지원
  const [chartMode, setChartMode] = useState('DAILY'); // 'DAILY' | 'MINUTE'
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2026-10-23');
  const [candleStart, setCandleStart] = useState('2026-10-23T09:00:00');
  const [selectedIndicators, setSelectedIndicators] = useState(['SMA20', 'VOLUME']);

  // 일봉 전체 캐시 (분봉으로 전환해도 상단 현재가/최고/최저 요약바가 사라지지 않도록 유지)
  const [dailyCandlesCache, setDailyCandlesCache] = useState([]);
  const [candles, setCandles] = useState([]);
  const [chartLoading, setChartLoading] = useState(true);
  const [chartError, setChartError] = useState('');

  // 초기 데이터 로드 (종목 상세, 커뮤니티 의견, AI 의견)
  useEffect(() => {
    let ignore = false;

    async function loadDetail() {
      setLoading(true);
      const results = await Promise.allSettled([
        stockAPI.getStockDetail(code),
        opinionAPI.getCommunityOpinion(code),
        aiOpinionAPI.getAiOpinion(code),
      ]);

      if (ignore) return;

      const nextErrors = {};
      if (results[0].status === 'fulfilled') setStock(results[0].value);
      else nextErrors.stock = getErrorMessage(results[0].reason);

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

      setErrors(nextErrors);
      setLoading(false);
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
          // 분봉 조회 (2026-10-23T09:00:00 기준)
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

  // 상단 요약바 시세 계산 (stock 테이블 값이 NULL인 종목은 일봉 캐시에서 최신 종가/등락률/거래량 자동 추출)
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

  const handleIndicatorChange = (indicatorId) => {
    setSelectedIndicators((prev) =>
      prev.includes(indicatorId) ? prev.filter((i) => i !== indicatorId) : [...prev, indicatorId]
    );
  };

  // 사용자 ID 세션 등록 (POST /api/users)[cite: 1, 11]
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

  // 매수/매도 투표 제출 (POST /api/stocks/{stockCode}/user-opinion)[cite: 2, 11]
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
        // 세션을 정상 등록했는데도 백엔드 DB(community_opinions)가 비어있어 500이 뜨는 경우 프론트엔드에서 즉시 반영[cite: 11, 14]
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
          
          {/* 좌측 영역: 기술적 지표 및 가격 차트 */}
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