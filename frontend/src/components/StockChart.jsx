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
  
  function StockChart({ stockName, selectedIndicators = [] }) {
    // 임시 날짜 라벨
    const labels = ['10-01', '10-02', '10-03', '10-04', '10-05', '10-06', '10-07'];
  
    // 1. 기본 종가 데이터 (항상 표시)
    const baseDataset = {
      label: `${stockName} 종가`,
      data: [68000, 68500, 69000, 68200, 69500, 71000, 72500],
      borderColor: '#111',
      backgroundColor: '#111',
      borderWidth: 2,
      tension: 0.1,
    };
  
    // 2. 기술적 지표별 임시 데이터셋 정의
    const indicatorDatasets = {
      MA20: {
        label: '이동평균선 (20일)',
        data: [67000, 67500, 68000, 68500, 69000, 69500, 70000],
        borderColor: '#E22926',
        borderWidth: 1.5,
        borderDash: [5, 5], // 점선 표현
        tension: 0.1,
        pointRadius: 0,
      },
      EMA20: {
        label: '지수평균선 (20일)',
        data: [67500, 68200, 68800, 68000, 69200, 70500, 71800],
        borderColor: '#F5A623',
        borderWidth: 1.5,
        tension: 0.1,
        pointRadius: 0,
      },
      BB: {
        label: '볼린저밴드 (상한)',
        data: [70000, 70500, 71000, 71500, 72000, 73000, 74000],
        borderColor: 'rgba(38, 121, 237, 0.5)',
        backgroundColor: 'rgba(38, 121, 237, 0.1)',
        borderWidth: 1,
        fill: true, // 선 아래 영역 색칠
        tension: 0.1,
        pointRadius: 0,
      }
    };
  
    // 3. 선택된 지표만 필터링하여 배열에 추가[cite: 30]
    const datasets = [baseDataset];
    selectedIndicators.forEach(ind => {
      if (indicatorDatasets[ind]) {
        datasets.push(indicatorDatasets[ind]);
      }
    });
  
    const data = { labels, datasets };
  
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