import hashlib
from pathlib import Path

def model_version(folder):
    folder=Path(folder)
    weights=sorted(folder.glob('*.safetensors'))
    if not weights: raise ValueError('Model weights missing')
    files=weights+[folder/'config.json']
    if (folder/'calibration.json').exists(): files.append(folder/'calibration.json')
    h=hashlib.sha256()
    for file in files:
        h.update(file.name.encode('utf-8'))
        with file.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
