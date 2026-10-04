import numpy as np
import pandas as pd
OHLCV = ['open', 'high', 'low', 'close', 'volume']
FEATURES = ['return', 'body', 'range', 'log_volume', 'return_3', 'return_6',
            'ma_distance_6', 'ma_distance_12', 'volatility_6', 'volume_relative_12',
            'close_location', 'session_progress']

def candles(path, stock_code='005930'):
    """Read start-stamped, KST one-minute bars; keep only complete 5m bars."""
    df = path.copy() if isinstance(path, pd.DataFrame) else pd.read_csv(path, dtype={'stock_code': str, 'market': str})
    required = {'timestamp', 'stock_code', 'market', *OHLCV}
    if not required.issubset(df.columns):
        raise ValueError(f'Required columns: {sorted(required)}')
    if not df.stock_code.eq(stock_code).all() or not df.market.eq('J').all():
        raise ValueError(f'Expected only stock {stock_code} / KRX J')
    ts = pd.to_datetime(df.timestamp, errors='raise')
    ts = ts.dt.tz_localize('Asia/Seoul') if ts.dt.tz is None else ts.dt.tz_convert('Asia/Seoul')
    # KIS may return the last trade second within each minute. The endpoint is
    # minute data, so normalize to the minute boundary before aggregation.
    ts = ts.dt.floor('min')
    df['timestamp'] = ts
    df[OHLCV] = df[OHLCV].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(df[OHLCV].to_numpy()).all():
        raise ValueError('Non-finite OHLCV')
    if ((df[['open','high','low','close']] <= 0).any(axis=1) |
        (df.volume < 0) | (df.high < df[['open','close','low']].max(axis=1)) |
        (df.low > df[['open','close','high']].min(axis=1))).any():
        raise ValueError('Invalid OHLCV')
    df = df.drop_duplicates()
    if df.timestamp.duplicated().any():
        raise ValueError('Conflicting duplicate timestamps')
    df = df.set_index('timestamp').sort_index()
    # Conservatively exclude opening minute, closing auction and nonstandard hours.
    # Fixed policy: minute starts 09:05 through 15:19 KST, weekdays only.
    df = df.between_time('09:05', '15:19')
    df = df[df.index.dayofweek < 5]
    bars = df.resample('5min', closed='left', label='right').agg(
        open=('open','first'), high=('high','max'), low=('low','min'),
        close=('close','last'), volume=('volume','sum'), count=('close','count'))
    bars = bars[bars['count'].eq(5)].drop(columns='count')
    if bars.empty:
        raise ValueError('No complete five-minute bars')
    return bars

def features(bars):
    # Segment by gaps as well as overnight boundaries. No filling missing bars.
    segment = bars.index.to_series().diff().ne(pd.Timedelta(minutes=5)).cumsum()
    prev = bars.close.groupby(segment).shift(1)
    f = pd.DataFrame(index=bars.index)
    f['return'] = np.log(bars.close / prev)
    f['body'] = np.log(bars.close / bars.open)
    f['range'] = (bars.high - bars.low) / bars.close
    f['log_volume'] = np.log1p(bars.volume)
    for n in (3, 6):
        f[f'return_{n}'] = np.log(bars.close / bars.close.groupby(segment).shift(n))
    for n in (6, 12):
        avg = bars.close.groupby(segment).transform(lambda s: s.rolling(n).mean())
        f[f'ma_distance_{n}'] = bars.close / avg - 1
    f['volatility_6'] = f['return'].groupby(segment).transform(lambda s: s.rolling(6).std(ddof=0))
    avg_volume = bars.volume.groupby(segment).transform(lambda s: s.rolling(12).mean())
    f['volume_relative_12'] = (bars.volume + 1) / (avg_volume + 1) - 1
    spread = (bars.high - bars.low).replace(0, np.nan)
    f['close_location'] = ((bars.close - bars.low) / spread).fillna(.5)
    f['session_progress'] = (bars.index.hour * 60 + bars.index.minute - 550) / 370
    return f[FEATURES]
