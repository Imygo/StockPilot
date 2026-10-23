import { useState, useEffect } from 'react';
import { stockAPI, opinionAPI, aiOpinionAPI, chartAPI, userAPI } from '../services/api';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ThumbsUp, ThumbsDown, Sparkles } from 'lucide-react';
import StockChart from '../components/StockChart';

function koreanDate(offset = 0) {
  const today = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
  const date = new Date(`${today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

function apiError(error) {
  return error.response?.data?.message
    ?? (error.code === 'ERR_NETWORK' ? '서버에 연결할 수 없습니다. 백엔드 실행 상태를 확인해주세요.' : error.message)
    ?? '요청에 실패했습니다.';
}

function StockDetail() {
  const { code } = useParams();
  return <StockDetailContent key={code} code={code} />;
}

function StockDetailContent({ code }) {
  const navigate = useNavigate();

  const [stock, setStock] = useState(null);
  const [community, setCommunity] = useState(null);
  const [aiOpinion, setAiOpinion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});
  const [voting, setVoting] = useState(false);
  const [voteError, setVoteError] = useState('');
  const [userId, setUserId] = useState('');
  const [registering, setRegistering] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState('');
  const [registrationError, setRegistrationError] = useState('');
  const [startDate, setStartDate] = useState(() => koreanDate(-30));
  const [endDate, setEndDate] = useState(() => koreanDate());
  const [candles, setCandles] = useState([]);
  const [chartLoading, setChartLoading] = useState(true);
  const [chartError, setChartError] = useState('');

  useEffect(() => {
    let ignore = false;
    async function loadDetail() {
      const results = await Promise.allSettled([
        stockAPI.getStockDetail(code),
        opinionAPI.getCommunityOpinion(code),
        aiOpinionAPI.getAiOpinion(code),
      ]);
      if (ignore) return;
      const setters = [setStock, setCommunity, setAiOpinion];
      const names = ['stock', 'community', 'ai'];
      const nextErrors = {};
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') setters[index](result.value);
        else nextErrors[names[index]] = apiError(result.reason);
      });
      setErrors(nextErrors);
      setLoading(false);
    }
    loadDetail();
    return () => { ignore = true; };
  }, [code]);

  useEffect(() => {
    let ignore = false;
    const timer = setTimeout(async () => {
      setCandles([]);
      setChartError('');
      setChartLoading(true);
      try {
        if (!startDate || !endDate || startDate > endDate) {
          throw new Error('시작일과 종료일을 확인해주세요.');
        }
        const rows = await chartAPI.getDailyChart(code, startDate, endDate);
        if (!ignore) setCandles(rows);
      } catch (err) {
        if (!ignore) setChartError(apiError(err));
      } finally {
        if (!ignore) setChartLoading(false);
      }
    }, 0);
    return () => { ignore = true; clearTimeout(timer); };
  }, [code, startDate, endDate]);

  const handleRegister = async (event) => {
    event.preventDefault();
    if (registering) return;
    setRegistering(true);
    setRegistrationError('');
    setRegistrationMessage('');
    try {
      await userAPI.registerUser(userId.trim());
      setRegistrationMessage('등록되었습니다. 의견을 선택해주세요.');
      setCommunity(previous => previous
        ? { ...previous, voted: false, myOpinion: null }
        : previous);
      setVoteError('');
    } catch (err) {
      setRegistrationError(apiError(err));
    } finally {
      setRegistering(false);
    }
  };

  const handleVote = async (opinion) => {
    if (voting || registering) return;
    setVoting(true);
    setVoteError('');
    try {
      const result = await opinionAPI.postUserOpinion(code, opinion);
      setCommunity(result);
      setErrors(previous => ({ ...previous, community: '' }));
    } catch (err) {
      setVoteError(err.response?.status === 401
        ? '사용자 등록 후 투표해주세요. 세션이 만료되었을 수 있습니다.'
        : apiError(err));
    } finally {
      setVoting(false);
    }
  };

  const buyPercent = community?.totalCount ? community.buy / community.totalCount * 100 : 0;
  const sellPercent = community?.totalCount ? community.sell / community.totalCount * 100 : 0;

  // 공통 카드 스타일
  const cardStyle = { backgroundColor: '#FFF', borderRadius: '15px', padding: '25px', boxShadow: '0 2px 10px rgba(0,0,0,0.05)', marginBottom: '20px' };

  if (loading) {
    return <p>종목 정보를 불러오는 중입니다.</p>;
  }

  if (!stock) {
    return <p role="alert">{errors.stock ?? '종목 정보가 없습니다.'}</p>;
  }

  return (
    <div style={{ backgroundColor: '#F7F9FA', minHeight: '100vh', padding: '40px 20px', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* 상단 헤더: 뒤로가기 및 기본 정보 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '20px' }}>
          <button onClick={() => navigate(-1)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', border: '1px solid #E0E0E0', borderRadius: '8px', backgroundColor: '#FFF', cursor: 'pointer' }}>
            <ArrowLeft size={16} /> 뒤로
          </button>
          <h1 style={{ margin: 0, fontSize: '28px' }}>{stock.stockName}</h1>
          <span style={{ color: '#666', fontSize: '16px' }}>{stock.stockCode}</span>
          <span style={{ backgroundColor: '#111', color: '#FFF', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold' }}>{stock.market}</span>
        </div>

        {/* 가격 정보 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '15px', marginBottom: '30px' }}>
          <span style={{ fontSize: '40px', fontWeight: 'bold' }}>{stock.currentPrice?.toLocaleString() ?? '-'}원</span>
          <span style={{ fontSize: '20px', fontWeight: 'bold', color: stock.changeAmount > 0 ? '#E22926' : stock.changeAmount < 0 ? '#2679ED' : '#666' }}>{stock.changeAmount > 0 ? '+' : ''}{stock.changeAmount?.toLocaleString() ?? '-'}원 ({stock.changeRate > 0 ? '+' : ''}{stock.changeRate ?? '-'}%)</span>
        </div>

        {/* 주요 지표 바 */}
        <div style={{ ...cardStyle, display: 'flex', justifyContent: 'space-between', padding: '20px 40px' }}>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>거래량</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>{stock.volume?.toLocaleString() ?? '-'}</div></div>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>시가총액</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>{stock.marketCap == null ? '-' : `${(stock.marketCap / 10000).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}조원`}</div></div>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>52주 최고</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>-</div></div>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>52주 최저</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>-</div></div>
        </div>

        {/* 본문 2단 그리드 */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
          
          {/* 좌측 영역: 지표 선택 및 차트 */}
          <div>
            <div style={{ ...cardStyle }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', display: 'flex', alignItems: 'center', gap: '5px' }}>📈 기술적 지표</h3>
              <p>지표 계산 준비 중입니다. 현재는 일봉 종가를 제공합니다.</p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                {[
                  { id: 'SMA20', label: '이동평균선 (20일)' }, { id: 'SMA60', label: '이동평균선 (60일)' }, { id: 'EMA20', label: '지수평균선 (20일)' },
                  { id: 'EMA60', label: '지수평균선 (60일)' }, { id: 'BOLLINGER_BANDS', label: '볼린저밴드' }, { id: 'RSI', label: 'RSI' },
                  { id: 'VOLUME', label: '거래량' }
                ].map(ind => (
                  <label key={ind.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
                    <input type="checkbox" disabled checked={false} readOnly style={{ width: '16px', height: '16px', accentColor: '#111' }} />
                    {ind.label}
                  </label>
                ))}
              </div>
            </div>
            
            <div style={{ ...cardStyle, minHeight: '400px' }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>가격 차트</h3>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
                <label>시작일 <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></label>
                <label>종료일 <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} /></label>
              </div>
              {chartLoading ? <p>차트를 불러오는 중입니다.</p>
                : chartError ? <p role="alert">{chartError}</p>
                : <StockChart stockName={stock.stockName} candles={candles} />}
            </div>
          </div>

          {/* 우측 영역: 의견 종합 */}
          <div>
            {/* 나의 의견 (중립 삭제됨) */}
            <div style={{ ...cardStyle }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>나의 의견</h3>
              <form onSubmit={handleRegister} style={{ marginBottom: '16px' }}>
                <label htmlFor="user-id">사용자 ID</label>
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <input id="user-id" value={userId} onChange={e => setUserId(e.target.value)} maxLength={50} required placeholder="새 사용자 ID" style={{ minWidth: 0, flex: 1 }} />
                  <button type="submit" disabled={registering || voting || !userId.trim()}>{registering ? '등록 중…' : '등록'}</button>
                </div>
                <small>처음 이용할 때 등록해주세요. 기존 ID 로그인 기능은 아직 제공되지 않습니다.</small>
              </form>
              {registrationMessage && <p role="status">{registrationMessage}</p>}
              {registrationError && <p role="alert">{registrationError}</p>}
              <p>내 의견: {community?.myOpinion ? ({ BUY: '매수', SELL: '매도', NEUTRAL: '중립' }[community.myOpinion]) : '선택하지 않음'}</p>
              {voteError && <p role="alert">{voteError}</p>}
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={() => handleVote('BUY')} disabled={voting || registering} aria-pressed={community?.myOpinion === 'BUY'} style={{ flex: 1, padding: '10px', backgroundColor: '#FFF', border: '1px solid #E0E0E0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', cursor: 'pointer', color: '#E22926', fontWeight: 'bold' }}>
                  <ThumbsUp size={16} /> 매수
                </button>
                <button onClick={() => handleVote('SELL')} disabled={voting || registering} aria-pressed={community?.myOpinion === 'SELL'} style={{ flex: 1, padding: '10px', backgroundColor: '#FFF', border: '1px solid #E0E0E0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', cursor: 'pointer', color: '#2679ED', fontWeight: 'bold' }}>
                  <ThumbsDown size={16} /> 매도
                </button>
              </div>
            </div>

            {/* AI 의견 */}
            <div style={{ ...cardStyle }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0, fontSize: '18px' }}>AI 의견</h3>
                <span style={{ backgroundColor: '#F0F0F0', fontSize: '12px', padding: '4px 8px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '3px' }}><Sparkles size={12} /> 베타</span>
              </div>
              {errors.ai ? <p role="alert">AI 의견 조회 실패: {errors.ai}</p>
                : <p>{aiOpinion?.aiOpinion ?? '아직 저장된 AI 의견이 없습니다.'}</p>}
            </div>

            {/* 커뮤니티 의견 (중립 삭제됨) */}
            <div style={{ ...cardStyle }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>커뮤니티 의견</h3>
              {errors.community && <p role="alert">커뮤니티 조회 실패: {errors.community}</p>}
              {community && <p>전체 {community.totalCount}명 · 중립 {community.neutral}명 포함</p>}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <span style={{ width: '50px', color: '#E22926', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px', fontWeight: 'bold' }}><ThumbsUp size={14}/> 매수</span>
                  <div style={{ flex: 1, backgroundColor: '#F0F0F0', height: '16px', borderRadius: '8px', overflow: 'hidden' }}><div style={{ width: `${buyPercent}%`, backgroundColor: '#E22926', height: '100%' }}></div></div>
                  <span style={{ width: '40px', textAlign: 'right', fontSize: '14px' }}>{community?.buy ?? '-'}명</span>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <span style={{ width: '50px', color: '#2679ED', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px', fontWeight: 'bold' }}><ThumbsDown size={14}/> 매도</span>
                  <div style={{ flex: 1, backgroundColor: '#F0F0F0', height: '16px', borderRadius: '8px', overflow: 'hidden' }}><div style={{ width: `${sellPercent}%`, backgroundColor: '#2679ED', height: '100%' }}></div></div>
                  <span style={{ width: '40px', textAlign: 'right', fontSize: '14px' }}>{community?.sell ?? '-'}명</span>
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