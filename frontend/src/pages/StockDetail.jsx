import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ThumbsUp, Minus, ThumbsDown, Sparkles } from 'lucide-react';
import StockChart from '../components/StockChart';

function StockDetail() {
  const { code } = useParams();
  const navigate = useNavigate();

  // 기술적 지표 체크박스 상태 관리 (다중 선택 가능하도록 배열 사용)[cite: 30, 32]
  const [selectedIndicators, setSelectedIndicators] = useState(['MA20', 'VOLUME']); 

  const handleIndicatorChange = (indicator) => {
    setSelectedIndicators(prev => 
      prev.includes(indicator) ? prev.filter(i => i !== indicator) : [...prev, indicator]
    );
  };

  // 공통 카드 스타일
  const cardStyle = { backgroundColor: '#FFF', borderRadius: '15px', padding: '25px', boxShadow: '0 2px 10px rgba(0,0,0,0.05)', marginBottom: '20px' };

  return (
    <div style={{ backgroundColor: '#F7F9FA', minHeight: '100vh', padding: '40px 20px', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* 상단 헤더: 뒤로가기 및 기본 정보[cite: 30] */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '20px' }}>
          <button onClick={() => navigate(-1)} style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '8px 12px', border: '1px solid #E0E0E0', borderRadius: '8px', backgroundColor: '#FFF', cursor: 'pointer' }}>
            <ArrowLeft size={16} /> 뒤로
          </button>
          <h1 style={{ margin: 0, fontSize: '28px' }}>삼성전자</h1>
          <span style={{ color: '#666', fontSize: '16px' }}>005930</span>
          <span style={{ backgroundColor: '#111', color: '#FFF', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: 'bold' }}>KOSPI</span>
        </div>

        {/* 가격 정보 */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '15px', marginBottom: '30px' }}>
          <span style={{ fontSize: '40px', fontWeight: 'bold' }}>72,500원</span>
          <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#E22926' }}>+1,500원 (+2.11%)</span>
        </div>

        {/* 주요 지표 바[cite: 30] */}
        <div style={{ ...cardStyle, display: 'flex', justifyContent: 'space-between', padding: '20px 40px' }}>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>거래량</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>15,234,567</div></div>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>시가총액</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>432.0조원</div></div>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>52주 최고</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>90,625원</div></div>
          <div><div style={{ color: '#666', fontSize: '14px', marginBottom: '8px' }}>52주 최저</div><div style={{ fontSize: '18px', fontWeight: 'bold' }}>54,375원</div></div>
        </div>

        {/* 본문 2단 그리드 */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' }}>
          
          {/* 좌측 영역: 지표 선택 및 차트[cite: 30, 32] */}
          <div>
            <div style={{ ...cardStyle }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px', display: 'flex', alignItems: 'center', gap: '5px' }}>📈 기술적 지표</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                {[
                  { id: 'MA20', label: '이동평균선 (20일)' }, { id: 'MA60', label: '이동평균선 (60일)' }, { id: 'EMA20', label: '지수평균선 (20일)' },
                  { id: 'EMA60', label: '지수평균선 (60일)' }, { id: 'BB', label: '볼린저밴드' }, { id: 'RSI', label: 'RSI' },
                  { id: 'VOLUME', label: '거래량' }
                ].map(ind => (
                  <label key={ind.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
                    <input type="checkbox" checked={selectedIndicators.includes(ind.id)} onChange={() => handleIndicatorChange(ind.id)} style={{ width: '16px', height: '16px', accentColor: '#111' }} />
                    {ind.label}
                  </label>
                ))}
              </div>
            </div>
            
            <div style={{ ...cardStyle, minHeight: '400px' }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>가격 차트</h3>
              <StockChart stockName="삼성전자" selectedIndicators={selectedIndicators} />
              /* props로 selectedIndicators 배열을 전달합니다[cite: 30] */
            </div>
          </div>

          {/* 우측 영역: 의견 종합[cite: 30] */}
          <div>
            {/* 나의 의견[cite: 30, 32] */}
            <div style={{ ...cardStyle }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>나의 의견</h3>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button style={{ flex: 1, padding: '10px', backgroundColor: '#FFF', border: '1px solid #E0E0E0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', cursor: 'pointer' }}><ThumbsUp size={16} /> 매수</button>
                <button style={{ flex: 1, padding: '10px', backgroundColor: '#FFF', border: '1px solid #E0E0E0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', cursor: 'pointer' }}><Minus size={16} /> 중립</button>
                <button style={{ flex: 1, padding: '10px', backgroundColor: '#FFF', border: '1px solid #E0E0E0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '5px', cursor: 'pointer' }}><ThumbsDown size={16} /> 매도</button>
              </div>
            </div>

            {/* AI 의견[cite: 30, 32] */}
            <div style={{ ...cardStyle }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0, fontSize: '18px' }}>AI 의견</h3>
                <span style={{ backgroundColor: '#F0F0F0', fontSize: '12px', padding: '4px 8px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '3px' }}><Sparkles size={12} /> 베타</span>
              </div>
              <button style={{ width: '100%', padding: '15px', backgroundColor: '#FFF', border: '1px solid #E0E0E0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
                <Sparkles size={18} /> AI 의견 받기
              </button>
            </div>

            {/* 커뮤니티 의견[cite: 30, 32] */}
            <div style={{ ...cardStyle }}>
              <h3 style={{ margin: '0 0 20px 0', fontSize: '18px' }}>커뮤니티 의견</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <span style={{ width: '50px', color: '#E22926', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px' }}><ThumbsUp size={14}/> 매수</span>
                  <div style={{ flex: 1, backgroundColor: '#F0F0F0', height: '16px', borderRadius: '8px', overflow: 'hidden' }}><div style={{ width: '60%', backgroundColor: '#E22926', height: '100%' }}></div></div>
                  <span style={{ width: '40px', textAlign: 'right', fontSize: '14px' }}>342명</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <span style={{ width: '50px', color: '#666', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px' }}><Minus size={14}/> 중립</span>
                  <div style={{ flex: 1, backgroundColor: '#F0F0F0', height: '16px', borderRadius: '8px', overflow: 'hidden' }}><div style={{ width: '20%', backgroundColor: '#666', height: '100%' }}></div></div>
                  <span style={{ width: '40px', textAlign: 'right', fontSize: '14px' }}>128명</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                  <span style={{ width: '50px', color: '#2679ED', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '14px' }}><ThumbsDown size={14}/> 매도</span>
                  <div style={{ flex: 1, backgroundColor: '#F0F0F0', height: '16px', borderRadius: '8px', overflow: 'hidden' }}><div style={{ width: '15%', backgroundColor: '#2679ED', height: '100%' }}></div></div>
                  <span style={{ width: '40px', textAlign: 'right', fontSize: '14px' }}>89명</span>
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