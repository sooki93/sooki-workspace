"""Cafe24's separate brief description, using entered facts without rewriting copy."""
import re
from app.services.text_format_service import format_text

SIZE_NOTICE='사이즈 측정 범위에 따라 오차 범위 내 차이가 있을 수 있습니다.'
COLOR_NOTICE='모니터 해상도에 따라 컬러 차이가 있을 수 있습니다.'
SILVER_NOTICE='92.5% 법정 순은 함량을 지키며 제품마다 925각인이 새겨집니다.'

def detail_facts(description):
    """Read only explicit labelled lines in the operator's detail info block."""
    facts={}; in_detail=False
    for line in description.splitlines():
        if re.fullmatch(r'detail\s+info\s*:?',line.strip(),re.I):
            in_detail=True
            continue
        if not in_detail: continue
        match=re.fullmatch(r'\s*(material|color|size)(?:\s*:\s*|\s+)(.+?)\s*',line,re.I)
        if match: facts.setdefault(match[1].lower(),match[2])
    return facts

def is_silver_925(material):
    # Exact material names: a silver colour, plating, or a mention in prose is insufficient.
    value=re.sub(r'[\s_-]+','',material).casefold()
    return value in {'925실버','실버925','925silver','silver925','sterlingsilver','sterlingsilver925','925sterlingsilver','스털링실버','스털링실버925','은925','925은'}

def brief_description(data):
    facts=detail_facts(data.get('description',''))
    material=facts.get('material') or data.get('material','')
    color=facts.get('color') or data.get('color','')
    size=facts.get('size') or data.get('size','')
    lines=['detail info',f'material {material}'.rstrip(),f'color {color}'.rstrip(),f'size {size}'.rstrip(),'',SIZE_NOTICE,COLOR_NOTICE]
    if is_silver_925(material): lines.append(SILVER_NOTICE)
    return '<div style="font-size:11px;line-height:1.8">'+format_text('\n'.join(lines))+'</div>'
