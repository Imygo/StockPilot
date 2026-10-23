import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
  } from 'chart.js';
  import { Line } from 'react-chartjs-2';
  
  // Chart.js 모듈 등록 (Filler는 볼린저밴드 등 영역 색칠에 사용)
  ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);
  
  function StockChart({ stockName, candles = [] }) {
    if (candles.length === 0) {
      return <p>선택한 기간에 저장된 일봉 데이터가 없습니다.</p>;
    }

    const data = {
      labels: candles.map(candle => candle.tradeDate),
      datasets: [{
        label: `${stockName} 종가`,
        data: candles.map(candle => candle.closePrice),
        borderColor: '#111',
        backgroundColor: '#111',
        borderWidth: 2,
        tension: 0.1,
      }],
    };

    const options = {
      responsive: true,
      maintainAspectRatio: false, // 부모 컨테이너(div) 크기에 맞춤
      plugins: {
        legend: { position: 'top' },
      },
      scales: {
        y: { beginAtZero: false } // 주가 차트이므로 0부터 시작하지 않음
      }
    };
  
    return (
        // 부모 컨테이너에 명시적인 높이(height)와 상대 위치(relative)를 지정합니다.
        <div style={{ position: 'relative', width: '100%', height: '400px' }}>
          <Line options={options} data={data} />
        </div>
      );
    }
    
    export default StockChart;