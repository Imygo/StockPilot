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


def split_frames(bars, train_start=None, train_end=None, val_end=None, test_end=None):
    """Split whole dates before feature/window/label construction."""
    supplied = [train_start, train_end, val_end, test_end]
    if any(value is not None for value in supplied):
        if not all(value is not None for value in supplied):
            raise ValueError('Provide all four: --train-start --train-end --val-end --test-end')
        from datetime import date
        try:
            start, end, validation_end, final = [date.fromisoformat(value) for value in supplied]
        except (ValueError, TypeError):
            raise ValueError('Split dates must be YYYY-MM-DD') from None
        if not start <= end < validation_end < final:
            raise ValueError('Require train_start <= train_end < val_end < test_end')
        days = bars.index.tz_convert('Asia/Seoul').date if bars.index.tz else bars.index.date
        parts = {
            'train': bars[(days >= start) & (days <= end)],
            'validation': bars[(days > end) & (days <= validation_end)],
            'test': bars[(days > validation_end) & (days <= final)],
        }
        for name, frame in parts.items():
            if frame.empty:
                raise ValueError(f'No data in requested {name} interval')
        return parts
    dates = np.unique(bars.index.date)
    if len(dates) < 10:
        raise ValueError('Need at least 10 trading days (more strongly recommended)')
    a, b = int(len(dates)*.7), int(len(dates)*.85)
    return {name: bars[np.isin(bars.index.date, days)] for name, days in
            zip(['train','validation','test'], [dates[:a], dates[a:b], dates[b:]])}


def fit_scaler(train):
    x = features(train).dropna().to_numpy()
    if len(x) == 0:
        raise ValueError('No training features')
    scale = x.std(axis=0)
    return {'mean': x.mean(axis=0).tolist(),
            'scale': np.where(scale > 0, scale, 1).tolist(), 'features': FEATURES}


def windows(bars, scaler, lookback, neutral_bps=0, stats=None):
    if lookback < 2:
        raise ValueError('lookback must be >= 2')
    if not np.isfinite(neutral_bps) or neutral_bps < 0:
        raise ValueError('neutral_bps must be finite and >= 0')
    f = features(bars)
    scaled = (f.to_numpy() - np.array(scaler['mean'])) / np.array(scaler['scale'])
    xs, ys, times = [], [], []
    eligible, excluded = 0, 0
    for i in range(lookback-1, len(bars)-1):
        start = i-lookback+1
        span = bars.index[start:i+2]
        if not (span.to_series().diff().iloc[1:] == pd.Timedelta(minutes=5)).all():
            continue
        x = scaled[start:i+1]
        if not np.isfinite(x).all():
            continue
        eligible += 1
        future_return = bars.close.iloc[i+1] / bars.close.iloc[i] - 1
        # Optional research task: condition on realized moves outside this band.
        # Never remove bars before creating windows or bridge the resulting gaps.
        if neutral_bps > 0 and abs(future_return) <= neutral_bps / 10000:
            excluded += 1
            continue
        xs.append(x)
        ys.append(int(bars.close.iloc[i+1] > bars.close.iloc[i]))
        times.append(str(bars.index[i]))
    if stats is not None:
        stats.update(eligible_windows=eligible, excluded_neutral=excluded,
                     retained_windows=len(ys), coverage=len(ys)/max(1, eligible))
    if not xs:
        raise ValueError('No windows; use more contiguous data or shorter lookback')
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.int64), times


def scores(y, probability, threshold=.5):
    p = np.asarray(probability)
    pred = (p >= threshold).astype(int)
    cm = [[int(((y == a) & (pred == b)).sum()) for b in (0,1)] for a in (0,1)]
    f1 = [2*cm[k][k] / max(1, 2*cm[k][k]+cm[k][1-k]+cm[1-k][k]) for k in (0,1)]
    q = np.clip(p, 1e-7, 1-1e-7)
    return {'accuracy': float((pred == y).mean()), 'macro_f1': float(np.mean(f1)),
            'f1_up': f1[1], 'confusion_matrix': cm,
            'log_loss': float(-(y*np.log(q)+(1-y)*np.log(1-q)).mean()),
            'samples': len(y), 'up_fraction': float(y.mean()),
            'predicted_up_fraction': float(pred.mean()),
            'recall_up': cm[1][1] / max(1, sum(cm[1])),
            'recall_down': cm[0][0] / max(1, sum(cm[0])),
            'threshold':float(threshold)}


def choose_threshold(validation_y, validation_probability):
    """Fixed coarse grid; ties prefer 0.5. Never pass test labels here."""
    if len(np.unique(validation_y)) != 2:
        raise ValueError('Validation must contain both classes to select a threshold')
    grid = np.linspace(.25, .75, 21)
    return float(max(grid, key=lambda t: (
        scores(validation_y, validation_probability, t)['macro_f1'], -abs(t-.5))))
