"""Per-symbol disk shards; windows never join stocks, sessions or splits."""
from collections import OrderedDict
import hashlib
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd
from .data import candles, features, FEATURES

# Drop absolute volume: shared features are dimensionless, relative quantities.
MULTI_FEATURES = [name for name in FEATURES if name != 'log_volume']


def validate_dates(train_start, train_end, val_end, test_end):
    a,b,c,d = [date.fromisoformat(s) for s in (train_start,train_end,val_end,test_end)]
    if not a <= b < c < d:
        raise ValueError('Require train_start <= train_end < val_end < test_end')
    if d >= pd.Timestamp.now(tz='Asia/Seoul').date():
        raise ValueError('test_end must be before today in KST')
    return a,b,c,d


def load_bars(raw, code, start, end):
    paths = sorted(Path(raw).glob(f'{code}_J_*.csv'))
    # Limit reads by validated day filenames, preserving stock identity checks.
    paths = [p for p in paths if start.replace('-','') <= p.stem[-8:] <= end.replace('-','')]
    if not paths:
        return None, []
    blocks, sources = [], []
    for path in paths:
        block = pd.read_csv(path,dtype={'stock_code':str,'market':str})
        if not block.stock_code.eq(code).all() or not block.market.eq('J').all():
            raise ValueError(f'Symbol/market mismatch in {path.name}')
        if not pd.to_datetime(block.timestamp).dt.strftime('%Y%m%d').eq(path.stem[-8:]).all():
            raise ValueError(f'Date mismatch in {path.name}')
        blocks.append(block)
        sources.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    frame = pd.concat(blocks,ignore_index=True)
    try:
        result = candles(frame,stock_code=code)
    except ValueError as exc:
        if str(exc) == 'No complete five-minute bars':
            return None, sources
        raise
    days = result.index.date
    return result[(days >= date.fromisoformat(start)) & (days <= date.fromisoformat(end))], sources


def make_rows(bars, lookback):
    if lookback < 2:
        raise ValueError('lookback must be >= 2')
    if bars.empty:
        return np.empty((0,len(MULTI_FEATURES)),np.float32), np.array([],np.int64), np.array([],np.int64)
    f = features(bars)[MULTI_FEATURES].to_numpy(dtype=np.float32)
    ends = np.arange(lookback-1,len(bars)-1,dtype=np.int64)
    begin = ends-lookback+1
    bad = np.r_[0,np.cumsum(~np.isfinite(f).all(axis=1))]
    segments = bars.index.to_series().diff().ne(pd.Timedelta(minutes=5)).cumsum().to_numpy()
    good = (bad[ends+1] == bad[begin]) & (segments[begin] == segments[ends+1])
    ends = ends[good]
    closing = bars.close.to_numpy()
    labels = (closing[ends+1] > closing[ends]).astype(np.int64)
    return f, ends, labels


def prepare(raw, codes, root, dates, lookback, min_train=50):
    a,b,c,d = validate_dates(**dates)
    manifest = {name:[] for name in ('train','validation','test')}
    excluded, sources, supported = {}, {}, []
    n, mean, m2 = 0, np.zeros(len(MULTI_FEATURES)), np.zeros(len(MULTI_FEATURES))
    for code in codes:
        bars, source = load_bars(raw,code,dates['train_start'],dates['test_end'])
        sources[code] = source
        if bars is None:
            excluded[code] = 'No complete data files'
            continue
        days = bars.index.date
        parts = {'train':bars[(days>=a)&(days<=b)],
                 'validation':bars[(days>b)&(days<=c)], 'test':bars[(days>c)&(days<=d)]}
        rows = {name:make_rows(frame,lookback) for name,frame in parts.items()}
        if len(rows['train'][1]) < min_train:
            excluded[code] = f'Fewer than {min_train} train windows'
            continue
        supported.append(code)
        # Streaming combined moments from train feature rows only, no test fit.
        values = rows['train'][0]
        values = values[np.isfinite(values).all(axis=1)].astype(np.float64)
        count, avg = len(values), values.mean(axis=0)
        delta = avg-mean
        m2 += ((values-avg)**2).sum(axis=0) + delta**2*n*count/(n+count)
        mean += delta*count/(n+count)
        n += count
        for name, (f, ends, y) in rows.items():
            path = Path(root)/'dataset'/name/code
            path.mkdir(parents=True,exist_ok=True)
            for key,array in [('features',f),('ends',ends),('labels',y)]:
                np.save(path/f'{key}.npy',array,allow_pickle=False)
            np.save(path/'times.npy',np.asarray(parts[name].index[ends].astype(str),dtype='U40'),allow_pickle=False)
            manifest[name].append({'stock_code':code, 'path':str(path.relative_to(root)),
                                   'samples':len(y), 'up':int(y.sum())})
        print(f'Prepared {code}: '+', '.join(f'{k}={len(v[1])}' for k,v in rows.items()),flush=True)
    if len(supported) < 2:
        raise ValueError(f'Need at least two symbols with enough train data; excluded={excluded}')
    for name,shards in manifest.items():
        if sum(s['samples'] for s in shards) == 0:
            raise ValueError(f'No usable {name} windows')
    scale = np.sqrt(np.maximum(m2/n,0))
    scaler = {'features':MULTI_FEATURES,'mean':mean.tolist(),
              'scale':np.where(scale>1e-12,scale,1).tolist(),'train_feature_rows':n}
    return manifest, scaler, supported, excluded, sources


class WindowDataset:
    """PyTorch map-style dataset without importing torch in data-only tests."""
    def __init__(self, root, shards, scaler, lookback):
        self._cache = OrderedDict()
        self.root, self.shards, self.lookback = Path(root), shards, lookback
        self.cumulative = np.cumsum([s['samples'] for s in shards])
        self.mean = np.asarray(scaler['mean'],np.float32)
        self.scale = np.asarray(scaler['scale'],np.float32)

    def __len__(self):
        return int(self.cumulative[-1]) if len(self.cumulative) else 0

    def arrays(self, shard):
        if shard in self._cache:
            self._cache.move_to_end(shard)
            return self._cache[shard]
        path = self.root/self.shards[shard]['path']
        arrays = tuple(np.load(path/f'{name}.npy',mmap_mode='r',allow_pickle=False)
                       for name in ('features','ends','labels'))
        self._cache[shard] = arrays
        if len(self._cache) > 8:
            _,old = self._cache.popitem(last=False)
            for value in old:
                value._mmap.close()
        return arrays

    def close(self):
        for arrays in self._cache.values():
            for value in arrays:
                value._mmap.close()
        self._cache.clear()

    def __del__(self):
        self.close()

    def __getitem__(self, i):
        if i < 0 or i >= len(self):
            raise IndexError(i)
        shard = int(np.searchsorted(self.cumulative,i,side='right'))
        local = i-(int(self.cumulative[shard-1]) if shard else 0)
        f,ends,y = self.arrays(shard)
        end = int(ends[local])
        x = np.asarray((f[end-self.lookback+1:end+1]-self.mean)/self.scale,dtype=np.float32)
        return x, np.float32(y[local])


def targets(root, shards):
    return np.concatenate([np.load(Path(root)/s['path']/'labels.npy',allow_pickle=False) for s in shards])
