import hashlib
import json
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    manifest=json.loads((root/'model-info/SHA256.json').read_text(encoding='utf-8'))
    for name,expected in manifest.items():
        path=root/'models/final-stockpilot-news-v1'/name
        if not path.is_file():raise ValueError('Missing model file: '+name)
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=expected:raise ValueError('Model checksum mismatch: '+name)
    print('All model files verified')
if __name__=='__main__':main()
