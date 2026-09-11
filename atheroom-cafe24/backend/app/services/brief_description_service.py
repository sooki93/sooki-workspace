"""Plain-text brief description for Cafe24 and downstream marketplace sync."""
import re

SIZE_NOTICE='사이즈 측정 범위에 따라 오차 범위 내 차이가 있을 수 있습니다.'
COLOR_NOTICE='모니터 해상도에 따라 컬러 차이가 있을 수 있습니다.'
SILVER_NOTICE='92.5% 법정 순은 함량을 지키며 제품마다 925각인이 새겨집니다.'

def is_silver_925(material):
    # Exact material names: a silver colour, plating, or a mention in prose is insufficient.
    value=re.sub(r'[\s_-]+','',material).casefold()
    return value in {'925실버','실버925','925silver','silver925','sterlingsilver','sterlingsilver925','925sterlingsilver','스털링실버','스털링실버925','은925','925은'}

def brief_description(data):
    description=data.get('description','')
    heading=re.search(r'^[ \t]*detail[ \t]+info[ \t]*:?[ \t]*\r?$',description,re.I|re.M)
    if heading:
        # Copy the operator's entire detail block verbatim, including notices,
        # blank lines, spacing and line endings. Formatting belongs to description.
        return description[heading.start():]
    # Products without a manually written block retain the existing fact fallback,
    # also as plain text. Never add HTML or encode literal text as HTML entities.
    material=data.get('material','')
    color=data.get('color','')
    size=data.get('size','')
    lines=['detail info',f'material {material}'.rstrip(),f'color {color}'.rstrip(),f'size {size}'.rstrip(),'',SIZE_NOTICE,COLOR_NOTICE]
    if is_silver_925(material): lines.append(SILVER_NOTICE)
    return '\n'.join(lines)
