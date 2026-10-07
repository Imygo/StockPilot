import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
  } from 'chart.js';
  import { Line } from 'react-chartjs-2';
  
  // Chart.js 모듈 등록
  ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend
  );
  
  function StockChart({ stockName }) {
    // 임시 차트 데이터 (추후 백엔드에서 PricePoint, IndicatorPoint 데이터를 받아와 매핑합니다[cite: 34, 40])
    const data = {
      labels: ['10-01', '10-02', '10-03', '10-04', '10-05', '10-06', '10-07'],
      datasets: [
        {
          label: `${stockName} 종가`,
          data: [68000, 68500, 69000, 68200, 69500, 70000, 70500],
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.5)',
          tension: 0.1,
        },
      ],
    };
  
    const options = {
      responsive: true,
      plugins: {
        legend: { position: 'top' },
        title: { display: true, text: '주가 변동 추이' },
      },
    };
  
    return <Line options={options} data={data} />;
  }
  
  export default StockChart;