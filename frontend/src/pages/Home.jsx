import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ArrowUpDown } from 'lucide-react';

function Home() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState('');
  const [marketFilter, setMarketFilter] = useState('ALL');
  const [sortType, setSortType] = useState('VOLUME_DESC');

  // 임시 종목 데이터 (Figma 화면 기준)
  const mockStocks = [
    { code: '005930', name: '삼성전자', market: 'KOSPI', price: 72500, changeAmount: 1500, changeRate: 2.11, volume: 15234567, marketCap: 432.0 },
    { code: '000660', name: 'SK하이닉스', market: 'KOSPI', price: 145000, changeAmount: -3000, changeRate: -2.03, volume: 5678901, marketCap: 105.6 },
    { code: '035720', name: '카카오', market: 'KOSPI', price: 42500, changeAmount: -1200, changeRate: -2.74, volume: 3456789, marketCap: 18.5 },
  ];

  const handleSearch = (e) => {
    e.preventDefault();
    if (!searchTerm.trim()) return; // 공백 검색 방지[cite: 29]
    console.log("검색 실행:", searchTerm);
  };

  return (
    <div style={{ backgroundColor: '#F7F9FA', minHeight: '100vh', padding: '40px 20px', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        
        {/* 헤더 타이틀 */}
        <div style={{ marginBottom: '30px' }}>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', margin: '0 0 10px 0' }}>주식 투자 도우미</h1>
          <p style={{ color: '#666', margin: 0 }}>실시간 주식 정보와 기술적 분석을 확인하세요</p>
        </div>

        {/* 1. 검색바[cite: 29] */}
        <form onSubmit={handleSearch} style={{ position: 'relative', marginBottom: '20px' }}>
          <Search style={{ position: 'absolute', left: '15px', top: '12px', color: '#999' }} size={20} />
          <input 
            type="text" 
            placeholder="종목명 또는 종목코드 검색" 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: '100%', padding: '15px 15px 15px 45px', borderRadius: '10px', border: '1px solid #E0E0E0', fontSize: '16px', boxSizing: 'border-box' }}
          />
        </form>

        {/* 2. 시장 필터 탭[cite: 29, 37] */}
        <div style={{ display: 'flex', gap: '10px', marginBottom: '30px', backgroundColor: '#EFEFEF', padding: '5px', borderRadius: '10px' }}>
          {['ALL', 'KOSPI', 'KOSDAQ'].map((market) => (
            <button
              key={market}
              onClick={() => setMarketFilter(market)}
              style={{
                flex: 1, padding: '10px', borderRadius: '8px', border: 'none', cursor: 'pointer', fontWeight: 'bold',
                backgroundColor: marketFilter === market ? '#FFF' : 'transparent',
                boxShadow: marketFilter === market ? '0 2px 4px rgba(0,0,0,0.1)' : 'none',
                color: marketFilter === market ? '#000' : '#666'
              }}
            >
              {market === 'ALL' ? '전체' : market === 'KOSPI' ? '코스피' : '코스닥'}
            </button>
          ))}
        </div>

        {/* 3. 종목 리스트 컨테이너[cite: 29] */}
        <div style={{ backgroundColor: '#FFF', borderRadius: '15px', padding: '20px', boxShadow: '0 2px 10px rgba(0,0,0,0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ fontSize: '18px', margin: 0 }}>인기 종목 (거래량 기준)</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', backgroundColor: '#F5F5F5', padding: '5px 10px', borderRadius: '8px' }}>
              <ArrowUpDown size={16} color="#666" />
              <select value={sortType} onChange={(e) => setSortType(e.target.value)} style={{ border: 'none', backgroundColor: 'transparent', outline: 'none', cursor: 'pointer' }}>
                <option value="VOLUME_DESC">거래량</option>
                <option value="PRICE_DESC">현재가 높은순</option>
                <option value="MARKET_CAP_DESC">시가총액 큰순</option>
              </select>
            </div>
          </div>

          {/* 리스트 아이템 */}
          {mockStocks.map(stock => (
            <div 
              key={stock.code} 
              onClick={() => navigate(`/stock/${stock.code}`)}
              style={{ display: 'flex', justifyContent: 'space-between', padding: '15px 0', borderBottom: '1px solid #F0F0F0', cursor: 'pointer' }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '18px', fontWeight: 'bold' }}>{stock.name}</span>
                  <span style={{ color: '#999', fontSize: '14px' }}>{stock.code}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#666' }}>
                  <span style={{ backgroundColor: '#F0F0F0', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold' }}>{stock.market}</span>
                  <span>거래량 {stock.volume.toLocaleString()}</span>
                  <span>시가총액 {stock.marketCap}조</span>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '5px' }}>{stock.price.toLocaleString()}원</div>
                <div style={{ fontSize: '14px', fontWeight: 'bold', color: stock.changeAmount > 0 ? '#E22926' : '#2679ED' }}>
                  {stock.changeAmount > 0 ? '+' : ''}{stock.changeAmount.toLocaleString()}원 ({stock.changeRate > 0 ? '+' : ''}{stock.changeRate}%)
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Home;