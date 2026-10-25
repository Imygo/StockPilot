import { useMemo } from 'react';
import ReactApexChart from 'react-apexcharts';

// --- 기술적 지표 수학 계산 헬퍼 함수들 ---
function calcSMA(data, period) {
  return data.map((item, idx) => {
    if (idx < period - 1) return { x: item.x, y: null };
    const slice = data.slice(idx - period + 1, idx + 1);
    const sum = slice.reduce((acc, cur) => acc + cur.close, 0);
    return { x: item.x, y: Math.round(sum / period) };
  });
}

function calcEMA(data, period) {
  const k = 2 / (period + 1);
  let ema = null;
  return data.map((item, idx) => {
    if (idx === 0) {
      ema = item.close;
      return { x: item.x, y: Math.round(ema) };
    }
    ema = item.close * k + ema * (1 - k);
    return { x: item.x, y: idx < period - 1 ? null : Math.round(ema) };
  });
}

function calcBollingerBands(data, period = 20, multiplier = 2) {
  const upper = [];
  const lower = [];
  data.forEach((item, idx) => {
    if (idx < period - 1) {
      upper.push({ x: item.x, y: null });
      lower.push({ x: item.x, y: null });
      return;
    }
    const slice = data.slice(idx - period + 1, idx + 1);
    const mean = slice.reduce((acc, cur) => acc + cur.close, 0) / period;
    const variance = slice.reduce((acc, cur) => acc + Math.pow(cur.close - mean, 2), 0) / period;
    const stdDev = Math.sqrt(variance);
    upper.push({ x: item.x, y: Math.round(mean + multiplier * stdDev) });
    lower.push({ x: item.x, y: Math.round(mean - multiplier * stdDev) });
  });
  return { upper, lower };
}

function calcRSI(data, period = 14) {
  const result = [];
  let gains = 0;
  let losses = 0;

  for (let i = 0; i < data.length; i++) {
    if (i === 0) {
      result.push({ x: data[i].x, y: null });
      continue;
    }
    const diff = data[i].close - data[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;

    if (i <= period) {
      gains += gain;
      losses += loss;
      if (i < period) {
        result.push({ x: data[i].x, y: null });
      } else {
        const avgGain = gains / period;
        const avgLoss = losses / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        result.push({ x: data[i].x, y: Number((100 - 100 / (1 + rs)).toFixed(2)) });
      }
    } else {
      gains = (gains * (period - 1) + gain) / period;
      losses = (losses * (period - 1) + loss) / period;
      const rs = losses === 0 ? 100 : gains / losses;
      result.push({ x: data[i].x, y: Number((100 - 100 / (1 + rs)).toFixed(2)) });
    }
  }
  return result;
}

function StockChart({ candles = [], chartMode = 'DAILY', selectedIndicators = [] }) {
  // 백엔드 응답(UpdateDailyChartResponse 또는 UpdateMinuteChartResponse) 정규화
  const normalizedData = useMemo(() => {
    return candles.map((item) => {
      const timeStr = item.tradeDate || item.candleStart;
      return {
        x: new Date(timeStr).getTime(),
        open: item.openPrice,
        high: item.highPrice,
        low: item.lowPrice,
        close: item.closePrice,
        volume: item.volume ?? null,
      };
    });
  }, [candles]);

  // 메인 캔들차트 + 오버레이 지표 시리즈 생성
  const mainSeries = useMemo(() => {
    const series = [
      {
        name: chartMode === 'DAILY' ? '일봉' : '분봉',
        type: 'candlestick',
        data: normalizedData.map((d) => ({
          x: d.x,
          y: [d.open, d.high, d.low, d.close],
        })),
      },
    ];

    if (chartMode === 'DAILY') {
      if (selectedIndicators.includes('SMA20')) {
        series.push({ name: 'SMA 20', type: 'line', data: calcSMA(normalizedData, 20) });
      }
      if (selectedIndicators.includes('SMA60')) {
        series.push({ name: 'SMA 60', type: 'line', data: calcSMA(normalizedData, 60) });
      }
      if (selectedIndicators.includes('EMA20')) {
        series.push({ name: 'EMA 20', type: 'line', data: calcEMA(normalizedData, 20) });
      }
      if (selectedIndicators.includes('EMA60')) {
        series.push({ name: 'EMA 60', type: 'line', data: calcEMA(normalizedData, 60) });
      }
      if (selectedIndicators.includes('BOLLINGER_BANDS')) {
        const bb = calcBollingerBands(normalizedData, 20, 2);
        series.push({ name: '볼린저 상단', type: 'line', data: bb.upper });
        series.push({ name: '볼린저 하단', type: 'line', data: bb.lower });
      }
    }

    return series;
  }, [normalizedData, chartMode, selectedIndicators]);

  const mainOptions = {
    chart: {
      type: 'candlestick',
      height: 350,
      toolbar: { show: true },
      animations: { enabled: false },
    },
    stroke: {
      width: mainSeries.map((s) => (s.type === 'candlestick' ? 1 : 2)),
      curve: 'smooth',
    },
    xaxis: {
      type: 'datetime',
    },
    yaxis: {
      tooltip: { enabled: true },
      labels: {
        formatter: (val) => (val ? `${Math.round(val).toLocaleString()}원` : ''),
      },
    },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#E22926', // 상승 빨강
          downward: '#2679ED', // 하락 파랑
        },
        wick: { useFillColor: true },
      },
    },
  };

  // 하단 보조 차트: 거래량 (VOLUME) & RSI
  const showVolume = chartMode === 'DAILY' && selectedIndicators.includes('VOLUME');
  const showRSI = chartMode === 'DAILY' && selectedIndicators.includes('RSI');

  const volumeSeries = useMemo(() => {
    if (!showVolume) return [];
    return [
      {
        name: '거래량',
        data: normalizedData.map((d) => ({ x: d.x, y: d.volume || 0 })),
      },
    ];
  }, [normalizedData, showVolume]);

  const rsiSeries = useMemo(() => {
    if (!showRSI) return [];
    return [
      {
        name: 'RSI (14)',
        data: calcRSI(normalizedData, 14),
      },
    ];
  }, [normalizedData, showRSI]);

  return (
    <div>
      {/* 1. 메인 가격 캔들차트 */}
      <ReactApexChart options={mainOptions} series={mainSeries} type="line" height={350} />

      {/* 2. 거래량 바 차트 (체크 시 하단에 표시) */}
      {showVolume && (
        <div style={{ marginTop: '10px' }}>
          <ReactApexChart
            options={{
              chart: { type: 'bar', height: 130, toolbar: { show: false }, animations: { enabled: false } },
              xaxis: { type: 'datetime' },
              yaxis: {
                labels: { formatter: (val) => (val ? `${Math.round(val / 10000).toLocaleString()}만` : '0') },
              },
              dataLabels: { enabled: false },
              colors: ['#6B7280'],
              title: { text: '거래량', style: { fontSize: '12px', color: '#6B7280' } },
            }}
            series={volumeSeries}
            type="bar"
            height={130}
          />
        </div>
      )}

      {/* 3. RSI 선 차트 (체크 시 하단에 표시) */}
      {showRSI && (
        <div style={{ marginTop: '10px' }}>
          <ReactApexChart
            options={{
              chart: { type: 'line', height: 130, toolbar: { show: false }, animations: { enabled: false } },
              stroke: { width: 2, curve: 'smooth' },
              xaxis: { type: 'datetime' },
              yaxis: { min: 0, max: 100, tickAmount: 2 },
              colors: ['#8B5CF6'],
              title: { text: 'RSI (14)', style: { fontSize: '12px', color: '#6B7280' } },
            }}
            series={rsiSeries}
            type="line"
            height={130}
          />
        </div>
      )}
    </div>
  );
}

export default StockChart;