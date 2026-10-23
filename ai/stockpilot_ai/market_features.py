"""Causal equal-weight stock-basket context; NOT official index returns."""
import numpy as np
import pandas as pd
from .multi_data import load_bars

HORIZONS=(1,3,6,12)
MARKETS=('KOSPI','KOSDAQ')
CONTEXT_COLUMNS=[f'{m}_{name}' for m in MARKETS for name in
                 [*[f'mean_{h}' for h in HORIZONS],*[f'coverage_{h}' for h in HORIZONS],'up_fraction','dispersion']]
FEATURE_NAMES=CONTEXT_COLUMNS+[f'own_return_{h}' for h in HORIZONS]+[f'relative_return_{h}' for h in HORIZONS]+[f'relative_valid_{h}' for h in HORIZONS]


def returns(bars):
    segment=bars.index.to_series().diff().ne(pd.Timedelta(minutes=5)).cumsum()
    return pd.DataFrame({f'r{h}':bars.close/bars.close.groupby(segment).shift(h)-1 for h in HORIZONS})


def aggregate(own,symbols):
    result=[]
    for market in MARKETS:
        codes=[s['stock_code'] for s in symbols if s['exchange']==market]
        parts=[]; first=None
        for h in HORIZONS:
            cols=[own[c][f'r{h}'].rename(c) for c in codes if c in own]
            panel=pd.concat(cols,axis=1) if cols else pd.DataFrame(index=pd.DatetimeIndex([],tz='Asia/Seoul'))
            coverage=panel.notna().sum(axis=1)/max(len(codes),1)
            parts.extend([panel.mean(axis=1).where(coverage>=.8,0).rename(f'{market}_mean_{h}'),
                          coverage.rename(f'{market}_coverage_{h}')])
            if h==1: first=(panel,coverage)
        panel,coverage=first
        up=panel.gt(0).sum(axis=1)/panel.notna().sum(axis=1).replace(0,np.nan)
        parts.extend([up.where(coverage>=.8,0).rename(f'{market}_up_fraction'),
                      panel.std(axis=1,ddof=0).where(coverage>=.8,0).rename(f'{market}_dispersion')])
        result.append(pd.concat(parts,axis=1))
    return pd.concat(result,axis=1).reindex(columns=CONTEXT_COLUMNS).fillna(0)


def build(raw,symbols,start,end,expected_sources=None):
    own={}; sources={}
    for i,s in enumerate(symbols):
        code=s['stock_code']; bars,files=load_bars(raw,code,start,end); sources[code]=files
        if expected_sources is not None:
            expected={v['file']:v['sha256'] for v in expected_sources[code]}
            if any(expected.get(v['file'])!=v['sha256'] for v in files):
                raise ValueError(f'{code}: raw data changed since preparation; prepare again')
            needed={name for name in expected if start.replace('-','')<=name[-12:-4]<=end.replace('-','')}
            if needed!={v['file'] for v in files}: raise ValueError(f'{code}: raw files missing since preparation')
        if bars is not None and not bars.empty: own[code]=returns(bars)
        if (i+1)%20==0: print(f'Market context: {i+1}/{len(symbols)} symbols',flush=True)
    return aggregate(own,symbols),own,sources


def encode(context,own,code,market,times):
    # Exact timestamp join. Never backfill, interpolate or use the next candle.
    index=pd.DatetimeIndex(times)
    base=context.reindex(index).fillna(0)
    local=own[code].reindex(index).to_numpy()
    if not np.isfinite(local).all(): raise ValueError(f'{code}: missing causal own-stock context')
    valid=np.column_stack([base[f'{market}_coverage_{h}'].to_numpy()>=.8 for h in HORIZONS])
    avg=base[[f'{market}_mean_{h}' for h in HORIZONS]].to_numpy()
    relative=np.where(valid,local-avg,0)
    result=np.column_stack([base.to_numpy(),local,relative,valid]).astype(np.float32)
    if not np.isfinite(result).all(): raise ValueError('Non-finite market features')
    return result


def encode_from_features(context,f,ends,market,times):
    """Same causal returns reconstructed from stored log returns for schema 9."""
    base=context.reindex(pd.DatetimeIndex(times)).fillna(0)
    local=np.column_stack([np.expm1(np.array([f[i-h+1:i+1,0].astype(np.float64).sum() for i in ends]))
                           for h in HORIZONS])
    valid=np.column_stack([base[f'{market}_coverage_{h}'].to_numpy()>=.8 for h in HORIZONS])
    avg=base[[f'{market}_mean_{h}' for h in HORIZONS]].to_numpy()
    result=np.column_stack([base.to_numpy(),local,np.where(valid,local-avg,0),valid]).astype(np.float32)
    if not np.isfinite(result).all(): raise ValueError('Non-finite market features')
    return result
