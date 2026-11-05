"""Transparent review hints, not sentiment overrides or semantic certainty."""
from news import clean

def assess(row, prediction):
    title=clean(row.get('title')); text=title+' '+clean(row.get('description'))
    reasons=[]; topics=[]
    target=row.get('aspect') or ('삼성전자' if row.get('stock_code','005930')=='005930' else row.get('stock_name',''))
    direct=bool(target) and target in title
    if any(w in text for w in ('코스피','주가','인버스','사이드카','증시')):
        topics.append('시장·가격 동향')
    if any(w in text for w in ('이해상충','주주환원','노조','집회','성과급 차별')):
        topics.append('지배구조·노사'); reasons.append('기업 위험과 단순 사실 보도를 구분해 검토')
    if any(w in text for w in ('시상','연구자','육성사업','포럼')):
        topics.append('연구지원·행사'); reasons.append('행사·홍보 어조와 구체적 사업 성과 구분 필요')
    if '인버스' in text or '곱버스' in text:
        reasons.append('파생상품 수익 방향과 대상 기업 주가 방향이 다를 수 있음')
    if any(w in text for w in ('배당','기술 개발','기술을 개발')):
        reasons.append('기술·주주환원 성과와 단순 일정 안내의 구분 필요')
    if any(w in text for w in ('호실적','호황','성장')) and any(w in text for w in ('우려','불확실','규제','악화','에도')):
        reasons.append('긍정 배경과 위험 또는 반대 내용이 함께 나타남')
    incidental=not direct and any(w in title for w in ('가구 분양','가구 공급','프리미어','아파트 분양')) and any(w in text for w in ('캠퍼스','인접','배후'))
    if incidental:
        relevance='단순 입지 언급 후보'; reasons.append('주택 입지 설명의 기업명 언급: 종목 감성 집계에서 보류')
    elif not direct:
        relevance='요약·간접 언급'; reasons.append('제목의 주체와 대상 기업에 대한 영향이 같은지 검토')
    else: relevance='제목에 대상 기업 명시'
    probs=sorted((prediction[k] for k in ('negative','neutral','positive')),reverse=True)
    if probs[0]<.7 or probs[0]-probs[1]<.15:
        reasons.append('분류 확률이 낮거나 두 분류의 차이가 작음')
    return dict(relevance_hint=relevance,topics=topics,review_reasons=reasons,
                review_required=bool(reasons),aggregate_hold=incidental,
                method='keyword review hints v1; not a trained relevance classifier')
