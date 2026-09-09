import re, html, copy
from collections import defaultdict, Counter
from bs4 import BeautifulSoup
from app.services.html_parser_service import sanitize

LABEL={'NAME':'상품명','DESCRIPTION':'상품 설명','WEARING':'착용 사진','PRODUCT':'제품 사진','DETAIL':'제품 사진 · 디테일/클로즈업','SIZE_REFERENCE':'사이즈 이미지','SIZE':'사이즈 안내','MATERIAL':'소재 안내','NOTICE':'구매 안내','SHIPPING':'배송 안내','RETURNS':'교환/반품 안내','AS':'수리 안내','BRAND':'브랜드 안내','UNKNOWN':'확인 필요','ETC':'기타 이미지','MAIN_CANDIDATE':'메인 사진'}

def image_pools(template,data,images):
    """A designated main photo has its own slot and is never consumed again below."""
    has_main=any(slot['type']=='MAIN_CANDIDATE' for slot in template.get('images',[]))
    pools=defaultdict(list)
    for image in sorted(images,key=lambda i:i.get('sort_order',0)):
        if has_main and image.get('id')==data.get('main_image_id'):
            pools['MAIN_CANDIDATE'].append(image)
            continue
        role=image.get('image_type','PRODUCT')
        if role=='MAIN_CANDIDATE': role='PRODUCT'
        pools[role].append(image)
    return pools

def render(template,data,images,preview=False):
    if not template: return '<p>반복해서 사용한 상품 형식이 아직 충분하지 않습니다.</p>'
    soup=BeautifulSoup(template['html'],'html.parser')
    by_role=image_pools(template,data,images)
    skeleton=defaultdict(list)
    for image in template['images']:
        node=soup.find('img',attrs={'data-image-slot':image['id']})
        if node: skeleton[image['type']].append(node)
    for role,nodes in skeleton.items():
        supplied=by_role.pop(role,[])
        # Allocate in encounter order but leave each repeated section at its original DOM position.
        # Extra photos extend the final matching section, never regroup all wearing/product photos.
        for index,node in enumerate(nodes):
            photo=supplied[index] if index<len(supplied) else None
            if photo is None:
                if preview:
                    placeholder=soup.new_tag('div'); placeholder['style']='padding:48px 20px;margin:16px 0;background:#eff2f5;color:#657080;font-size:16px;text-align:center'
                    placeholder.string=LABEL.get(role,'상품 이미지')+(f' {index+1}' if len(nodes)>1 else '')
                    node.replace_with(placeholder)
                else: node.decompose()
                continue
            node.attrs.pop('data-image-slot',None)
            node['src']=photo['file_url']; node['alt']=data.get('product_name','')
        if len(supplied)>len(nodes) and nodes:
            last=nodes[-1]
            for photo in supplied[len(nodes):]:
                clone=copy.copy(last); clone['src']=photo['file_url']
                last.insert_after(clone); last=clone
    result=str(soup)
    values={'NAME':data.get('product_name',''),'DESCRIPTION':data.get('description',''),'SIZE':data.get('size',''),'MATERIAL':data.get('material','')}
    used=set()
    replacements=dict(template['fixed_blocks'])
    for slot in template['slots']:
        role=slot['role']
        replacements[slot['id']]=values.get(role,'') if role not in used else ''
        if preview and not replacements[slot['id']] and role not in used: replacements[slot['id']]=LABEL.get(role,'확인할 내용')+' 입력 영역'
        used.add(role)
    result=re.sub(r'\{\{(t\d+)\}\}',lambda m:html.escape(str(replacements.get(m[1],''))).replace('\n','<br>'),result)
    return sanitize(result)

def compare(template,data,images):
    warnings=[]
    expected=Counter(i['type'] for i in template.get('images',[]))
    pools=image_pools(template,data,images)
    for role,count in expected.items():
        actual=len(pools.get(role,[]))
        if actual<count: warnings.append(f'{LABEL.get(role,"상품 사진")} 영역 {count}곳 중 {count-actual}곳에 사진이 필요합니다.')
    avg=template.get('description_rules',{}).get('average_length',0)
    if avg and not .5*avg<=len(data.get('description',''))<=1.8*avg: warnings.append('상품 설명 길이가 기존 상품과 다릅니다.')
    name_avg=template.get('product_name_rules',{}).get('average_length',0)
    if name_avg and len(data.get('product_name',''))>max(name_avg*2,30): warnings.append('상품명이 기존 상품보다 깁니다.')
    if template.get('unresolved'): warnings.append('기존 형식에 확인되지 않은 문구가 있습니다. 형식을 다시 분석해주세요.')
    return warnings
