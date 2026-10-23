"""Frozen inference transformations extracted unchanged from training code."""

import numpy as np

def encode(x):
    # Same causal window; recent level, mean, variability and change.
    if x.ndim!=3 or x.shape[1]<2 or not np.isfinite(x).all():
        raise ValueError('Expected finite window features')
    return np.concatenate([x[:,-1],x.mean(axis=1),x.std(axis=1),x[:,-1]-x[:,0]],axis=1)

def matrix(x, z, prior, exchange):
    return np.column_stack([x, np.full(len(x), prior),
                            np.full(len(x), exchange == 'KOSDAQ'), z]).astype(np.float32)
