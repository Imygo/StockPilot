import { useEffect, useState } from 'react';
import ReactApexChart from 'react-apexcharts';
// import { chartAPI } from '../services/api'; // 백엔드 연동 시 주석 해제

function StockChart({ stockCode, startDate, endDate, selectedIndicators = [] }) {
  const [series, setSeries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 1. 임시 데이터 생성 (백엔드 API 연동 전 UI 테스트용)
    const fetchChartData = () => {
      setLoading(true);
      
      // 캔들차트 데이터 (시가, 고가, 저가, 종가)
      const candleData = [
        { x: new Date('2026-10-01').getTime(), y: [68000, 69000, 67500, 68500] },
        { x: new Date('2026-10-02').getTime(), y: [68500, 69500, 68000, 69000] },
        { x: new Date('2026-10-03').getTime(), y: [69000, 70000, 68500, 68200] },
        { x: new Date('2026-10-04').getTime(), y: [68200, 69500, 68000, 69500] },
        { x: new Date('2026-10-05').getTime(), y: [69500, 71500, 69000, 71000] },
        { x: new Date('2026-10-06').getTime(), y: [71000, 73000, 70500, 72500] },
      ];

      // 기본 시리즈(일봉) 세팅 -> ApexCharts에서는 혼합 차트를 위해 type을 명시합니다.
      const newSeries = [
        {
          name: '일봉',
          type: 'candlestick',
          data: candleData
        }
      ];

      // 2. 보조지표별 임시 데이터 (선 차트용)
      const indicatorDataMap = {
        MA20: [
          { x: new Date('2026-10-01').getTime(), y: 67000 },
          { x: new Date('2026-10-02').getTime(), y: 67500 },
          { x: new Date('2026-10-03').getTime(), y: 68000 },
          { x: new Date('2026-10-04').getTime(), y: 68500 },
          { x: new Date('2026-10-05').getTime(), y: 69000 },
          { x: new Date('2026-10-06').getTime(), y: 69500 },
        ],
        EMA20: [
          { x: new Date('2026-10-01').getTime(), y: 67500 },
          { x: new Date('2026-10-02').getTime(), y: 68200 },
          { x: new Date('2026-10-03').getTime(), y: 68800 },
          { x: new Date('2026-10-04').getTime(), y: 68000 },
          { x: new Date('2026-10-05').getTime(), y: 69200 },
          { x: new Date('2026-10-06').getTime(), y: 70500 },
        ]
      };

      // 3. 선택된 지표(`selectedIndicators`)가 배열에 있으면 선 차트(line)로 추가
      selectedIndicators.forEach(ind => {
        if (indicatorDataMap[ind]) {
          newSeries.push({
            name: ind,
            type: 'line',
            data: indicatorDataMap[ind]
          });
        }
      });

      /* 
       * 실제 API 연동 시 위 로직은 다음과 같이 교체됩니다:
       * const candleRes = await chartAPI.getDailyChart(stockCode, startDate, endDate);
       * const indicatorRes = await chartAPI.getIndicatorChart(stockCode, startDate, endDate, selectedIndicators);
       * -> 받은 데이터를 newSeries 배열 포맷에 맞게 map()으로 가공
       */

      setSeries(newSeries);
      setLoading(false);
    };

    fetchChartData();
  }, [stockCode, startDate, endDate, selectedIndicators]);

  // 차트 옵션 설정
  const options = {
    chart: {
      type: 'line', // 혼합 차트를 그릴 때는 최상위 type을 'line'으로 둡니다.
      height: 400,
      toolbar: { show: false }
    },
    stroke: {
      // 캔들차트 테두리는 얇게(1), 추가되는 꺾은선(보조지표)들은 두껍게(2)
      width: [1, 2, 2, 2, 2],
      curve: 'smooth'
    },
    xaxis: {
      type: 'datetime',
    },
    yaxis: {
      tooltip: { enabled: true }
    },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#E22926', // 한국 주식 시장 상승(빨강)
          downward: '#2679ED' // 한국 주식 시장 하락(파랑)
        },
        wick: { useFillColor: true }
      }
    }
  };

  if (loading) return <div style={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>차트를 불러오는 중...</div>;

  return (
    <div style={{ width: '100%', height: '400px' }}>
      <ReactApexChart 
        options={options} 
        series={series} 
        type="line" // 혼합 차트 필수 설정
        height={400} 
      />
    </div>
  );
}

export default StockChart;