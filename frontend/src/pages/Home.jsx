import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowUpDown, BarChart2 } from 'lucide-react';
import { stockAPI, getErrorMessage } from '../services/api';

// DB(daily_chart_data)에 차트 데이터가 풍부하게 들어있는 시연 핵심 종목 코드
const DEMO_READY_CODES = new Set(['005930', '000660', '003490', '002720', '003280']);

function Home() {
  const navigate = useNavigate();

  const [searchInput, setSearchInput] = useState('');
  const [appliedKeyword, setAppliedKeyword] = useState(undefined);
  const [market, setMarket] = useState('ALL');
  const [sort, setSort] = useState('VOLUME_DESC');

  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let ignore = false;

    const fetchStocks = async () => {
      setLoading(true);
      setError('');
      try {
        const data = await stockAPI.getStocks({
          keyword: appliedKeyword,
          market,
          sort,
        });
        if (!ignore) {
          setStocks(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (!ignore) {
          setStocks([]);
          setError(getErrorMessage(err));
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };

    fetchStocks();
    return () => {
      ignore = true;
    };
  }, [appliedKeyword, market, sort]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (searchInput === '') {
      setAppliedKeyword(undefined);
      if (sort === 'SEARCH_PRIORITY') setSort('VOLUME_DESC');
      return;
    }
    setAppliedKeyword(searchInput);
    setSort('SEARCH_PRIORITY');
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setSearchInput(val);
    if (val === '' && appliedKeyword !== undefined) {
      setAppliedKeyword(undefined);
      if (sort === 'SEARCH_PRIORITY') setSort('VOLUME_DESC');
    }
  };

  const formatPrice = (price) =>
    price !== null && price !== undefined ? `${price.toLocaleString()}원` : '상세 차트 확인';
  const formatVolume = (vol) => (vol !== null && vol !== undefined ? vol.toLocaleString() : '-');
  const formatMarketCap = (cap) => {
    if (cap === null || cap === undefined) return '-';
    if (cap >= 10000) return `${(cap / 10000).toFixed(2)}조원`;
    return `${cap.toLocaleString()}억원`;
  };

  return (
    <div style={{ backgroundColor: '#F7F9FA', minHeight: '100vh', padding: '50px 20px', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        
        {/* 상단 타이틀 */}
        <div style={{ textAlign: 'center', marginBottom: '35px' }}>
          <h1 style={{ fontSize: '32px', fontWeight: 'bold', margin: '0 0 10px 0', color: '#111' }}>주식 투자 도우미</h1>
          <p style={{ color: '#666', fontSize: '15px', margin: 0 }}>실시간 주식 정보와 기술적 분석을 확인하세요</p>
        </div>

        {/* 검색창 */}
        <form onSubmit={handleSearchSubmit} style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', backgroundColor: '#FFF', border: '1px solid #E5E7EB', borderRadius: '12px', padding: '12px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
            <Search size={18} color="#9CA3AF" style={{ marginRight: '10px' }} />
            <input
              type="text"
              placeholder="종목명 또는 종목코드 검색 (예: 삼성, 000660)"
              value={searchInput}
              onChange={handleInputChange}
              style={{ border: 'none', outline: 'none', width: '100%', fontSize: '15px', color: '#111' }}
            />
            {searchInput && (
              <button
                type="button"
                onClick={() => {
                  setSearchInput('');
                  setAppliedKeyword(undefined);
                  setSort('VOLUME_DESC');
                }}
                style={{ border: 'none', background: 'none', color: '#999', cursor: 'pointer', fontSize: '13px', whiteSpace: 'nowrap' }}
              >
                초기화
              </button>
            )}
          </div>
        </form>

        {/* 시장 구분 탭 */}
        <div style={{ display: 'flex', backgroundColor: '#EFEFEF', borderRadius: '12px', padding: '4px', marginBottom: '25px' }}>
          {[
            { id: 'ALL', label: '전체' },
            { id: 'KOSPI', label: '코스피' },
            { id: 'KOSDAQ', label: '코스닥' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setMarket(tab.id)}
              style={{
                flex: 1,
                padding: '10px 0',
                border: 'none',
                borderRadius: '8px',
                backgroundColor: market === tab.id ? '#FFF' : 'transparent',
                color: '#111',
                fontWeight: market === tab.id ? 'bold' : 'normal',
                fontSize: '14px',
                cursor: 'pointer',
                boxShadow: market === tab.id ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* 종목 리스트 카드 */}
        <div style={{ backgroundColor: '#FFF', borderRadius: '16px', padding: '25px', boxShadow: '0 2px 10px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 'bold', color: '#111' }}>
              {appliedKeyword ? `'${appliedKeyword}' 검색 결과` : '인기 종목'}
            </h2>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', border: '1px solid #E5E7EB', borderRadius: '8px', padding: '6px 12px', backgroundColor: '#FAFAFA' }}>
              <ArrowUpDown size={14} color="#555" />
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value)}
                style={{ border: 'none', background: 'transparent', outline: 'none', fontSize: '13px', fontWeight: 'bold', color: '#333', cursor: 'pointer' }}
              >
                <option value="VOLUME_DESC">거래량</option>
                <option value="SEARCH_PRIORITY">검색 정확도</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#666', fontSize: '15px' }}>
              종목 목록을 불러오는 중입니다...
            </div>
          ) : error ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#E22926', fontSize: '15px' }} role="alert">
              {error}
            </div>
          ) : stocks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#888', fontSize: '15px' }}>
              조회된 종목이 없습니다.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {stocks.map((item) => {
                const isUp = item.changeRate > 0;
                const isDown = item.changeRate < 0;
                const priceColor = isUp ? '#E22926' : isDown ? '#2679ED' : '#666';
                const hasChartData = DEMO_READY_CODES.has(item.stockCode);

                return (
                  <div
                    key={item.stockCode}
                    onClick={() => navigate(`/stock/${item.stockCode}`)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '16px 20px',
                      border: '1px solid #F0F0F0',
                      borderRadius: '12px',
                      cursor: 'pointer',
                      transition: 'background-color 0.15s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#F9FAFB')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#FFF')}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{ fontSize: '16px', fontWeight: 'bold', color: '#111' }}>{item.stockName}</span>
                        <span style={{ fontSize: '13px', color: '#888' }}>{item.stockCode}</span>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 'bold',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor: item.market === 'KOSPI' ? '#111' : '#4B5563',
                            color: '#FFF',
                          }}
                        >
                          {item.market}
                        </span>
                        {hasChartData && (
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 'bold',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              backgroundColor: '#EEF2FF',
                              color: '#4F46E5',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '3px',
                            }}
                          >
                            <BarChart2 size={11} /> 차트 데이터 보유
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '12px', color: '#888' }}>
                        거래량 {formatVolume(item.volume)} · 시가총액 {formatMarketCap(item.marketCap)}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div
                        style={{
                          fontSize: item.currentPrice !== null ? '17px' : '14px',
                          fontWeight: 'bold',
                          color: item.currentPrice !== null ? '#111' : '#4F46E5',
                          marginBottom: '4px',
                        }}
                      >
                        {formatPrice(item.currentPrice)}
                      </div>
                      {item.changeRate !== null && item.changeRate !== undefined ? (
                        <div style={{ fontSize: '13px', fontWeight: 'bold', color: priceColor }}>
                          {item.changeAmount > 0
                            ? `+${item.changeAmount.toLocaleString()}원`
                            : `${item.changeAmount?.toLocaleString() ?? 0}원`}{' '}
                          ({item.changeRate > 0 ? `+${item.changeRate}%` : `${item.changeRate}%`})
                        </div>
                      ) : (
                        <div style={{ fontSize: '12px', color: '#AAA' }}>일봉 기준 시세 제공</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

export default Home;