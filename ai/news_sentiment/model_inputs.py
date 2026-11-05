"""One input contract shared by training and prediction."""
from news import clean

INPUT_FORMAT = 'target-text-pair-v1'
MARKED_FORMAT = 'target-marked-pair-v2'
MAX_LENGTH = 256

def input_pair(row):
    target = clean(row.get('aspect'))
    if not target and row.get('stock_code') == '005930':
        target = '삼성전자'
    text = clean(row.get('title')) + '\n' + clean(row.get('description'))
    if not target or not text.strip():
        raise ValueError('Both target (aspect) and text are required')
    return target, text.strip()

def encode_rows(tokenizer, rows, input_format=INPUT_FORMAT, **kwargs):
    pairs = [input_pair(row) for row in rows]
    if input_format == MARKED_FORMAT:
        pairs = [(target, text.replace(target, ' [대상기업] '+target+' [/대상기업] ')) for target,text in pairs]
    elif input_format != INPUT_FORMAT:
        raise ValueError('Unsupported input format')
    return tokenizer([p[0] for p in pairs], [p[1] for p in pairs],
                     truncation='only_second', max_length=MAX_LENGTH, **kwargs)
