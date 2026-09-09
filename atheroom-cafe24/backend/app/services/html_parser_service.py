import re, hashlib, copy
from collections import Counter
from bs4 import BeautifulSoup, NavigableString, Tag, Comment
import bleach
from bleach.css_sanitizer import CSSSanitizer

TAGS=['div','p','span','img','table','tbody','thead','tfoot','tr','td','th','br','strong','b','em','i','u','section','article','h1','h2','h3','h4','h5','h6','ul','ol','li','hr','a','center','figure','figcaption']
CSS=CSSSanitizer(allowed_css_properties=['color','background-color','font-family','font-size','font-weight','font-style','line-height','text-align','text-decoration','vertical-align','width','max-width','min-width','height','max-height','margin','margin-top','margin-bottom','margin-left','margin-right','padding','padding-top','padding-bottom','padding-left','padding-right','border','border-top','border-bottom','border-collapse','border-spacing','display','box-sizing','letter-spacing','white-space'])
LABELS={'size':'SIZE','사이즈':'SIZE','material':'MATERIAL','소재':'MATERIAL','notice':'NOTICE','안내':'NOTICE','배송 안내':'SHIPPING','shipping':'SHIPPING','교환/반품 안내':'RETURNS','교환 및 반품':'RETURNS','a/s 안내':'AS'}
FIXED_ROLES={'NOTICE','SHIPPING','RETURNS','AS','BRAND','LABEL'}

def sanitize(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for node in soup(['script','iframe','object','embed','style','link','meta','form','input','button','svg','math','noscript']): node.decompose()
    for comment in soup.find_all(string=lambda t:isinstance(t,Comment)): comment.extract()
    return bleach.clean(str(soup),tags=TAGS,attributes={'*':['class','style','align'], 'img':['src','alt','width','height'], 'a':['href','title'], 'td':['colspan','rowspan','width'], 'th':['colspan','rowspan']},protocols=['https'],css_sanitizer=CSS,strip=True)

def infer_group(name):
    for group, words in [('PIERCING',['piercing','피어싱']),('EARRING',['earring','귀걸이','이어링']),('NECKLACE',['necklace','목걸이','네크리스']),('BRACELET',['bracelet','팔찌','브레이슬릿']),('HAIR',['hair','헤어','집게핀']),('RING',['ring','반지','링'])]:
        if any(w in name.lower() for w in words): return group
    return 'ETC'

def parse_html(raw, product_name=''):
    if len(raw)>2_000_000: raise ValueError('html too large')
    clean=sanitize(raw)
    soup=BeautifulSoup(clean,'html.parser')
    if not soup.find(): raise ValueError('empty detail')
    for link in soup.find_all('a'):
        link.attrs.pop('href',None); link.attrs.pop('title',None)
    slots=[]; images=[]; context='DESCRIPTION'
    for node in list(soup.descendants):
        if isinstance(node,Tag) and node.name=='img':
            id=f'i{len(images)}'
            src=node.get('src','')
            if src.startswith('//'): src='https:'+src
            hint=' '.join(node.get('class',[]))+' '+node.get('alt','')
            role='MAIN_CANDIDATE' if re.search(r'(?:^|\s)(?:main-photo|main|메인)(?:\s|$)',hint,re.I) else 'WEARING' if re.search('wear|착용|model',hint,re.I) else 'DETAIL' if re.search('detail|디테일|closeup|close-up|클로즈업',hint,re.I) else 'SIZE_REFERENCE' if re.search('size|사이즈',hint,re.I) else 'PRODUCT'
            images.append({'id':id,'type':role,'source_url':src})
            node.attrs.pop('alt',None); node['src']=''; node['data-image-slot']=id
        elif isinstance(node,NavigableString) and node.strip():
            value=str(node).strip(); id=f't{len(slots)}'; label=LABELS.get(value.lower())
            if label: context=label; role='LABEL'
            elif product_name and value==product_name: role='NAME'
            else: role=context
            slots.append({'id':id,'text':value,'role':role})
            node.replace_with('{{'+id+'}}')
    if not slots and not images: raise ValueError('unreadable detail')
    # Structural signature carries no product values, URLs, IDs or numeric classes.
    tokens=[]
    for node in soup.find_all(True):
        classes='.'.join(sorted(re.sub(r'\d+','N',v) for v in node.get('class',[])))
        depth=len(list(node.parents))
        tokens.append(f'{depth}:{node.name}.{classes}:{node.get("style","")}')
    return {'html':str(soup),'tokens':tokens,'slots':slots,'images':images,'group':infer_group(product_name),'name_length':len(product_name),'name_pattern':re.sub(r'[가-힣A-Za-z0-9]+','{{WORD}}',product_name),'description_length':sum(len(s['text']) for s in slots if s['role']=='DESCRIPTION'),'sentence_count':sum(max(1,len(re.findall(r'[.!?。](?:\s|$)',s['text']))) for s in slots if s['role']=='DESCRIPTION')}

def section_order(parsed):
    pairs={s['id']:s['role'] for s in parsed['slots']}
    pairs.update({i['id']:i['type'] for i in parsed['images']})
    result=[]
    for match in re.finditer(r'\{\{(t\d+)\}\}|data-image-slot="(i\d+)"',parsed['html']):
        role=pairs.get(match[1] or match[2],'UNKNOWN')
        if role=='LABEL': continue
        if not result or result[-1]!=role: result.append(role)
    return result

def compile_template(samples):
    representative=copy.deepcopy(samples[0]['parsed'])
    repeats=Counter()
    for s in samples:
        repeats.update(set((slot['role'],slot['text']) for slot in s['parsed']['slots'] if slot['role'] in FIXED_ROLES))
    fixed={}; fixed_roles={}; slots=[]; unresolved=[]
    for slot in representative['slots']:
        key=(slot['role'],slot['text'])
        # Only narrowly identified common policies/labels can survive. All other source text is discarded.
        if slot['role'] in FIXED_ROLES and repeats[key]>=3:
            fixed[slot['id']]=slot['text']; fixed_roles[slot['id']]=slot['role']
        else:
            role=slot['role']
            if role in FIXED_ROLES or role=='UNKNOWN': unresolved.append(slot['id']); role='UNKNOWN'
            slots.append({'id':slot['id'],'role':role})
    return {'html':representative['html'],'slots':slots,'fixed_blocks':fixed,'fixed_roles':fixed_roles,'images':[{'id':i['id'],'type':i['type']} for i in representative['images']], 'section_order':section_order(representative),'unresolved':unresolved,'source_product_ids':[s['product_no'] for s in samples], 'description_rules':{'average_length':round(sum(s['parsed']['description_length'] for s in samples)/len(samples)),'average_sentences':round(sum(s['parsed']['sentence_count'] for s in samples)/len(samples),1),'guidance':samples[0]['parsed'].get('description_rules','제품 구조와 특징 중심의 중립적 문체')},'product_name_rules':{'average_length':round(sum(s['parsed']['name_length'] for s in samples)/len(samples)),'guidance':samples[0]['parsed'].get('product_name_rules','제품 특징과 상품군을 간결하게 표기')},'image_rules':dict(Counter(i['type'] for i in representative['images']))}
