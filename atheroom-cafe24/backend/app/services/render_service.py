import re, html, copy
from collections import defaultdict, Counter
from bs4 import BeautifulSoup
from app.services.html_parser_service import sanitize, LABELS
from app.services.text_format_service import format_text,FONT_SIZE

OMITTED_DETAIL_ROLES={'MATERIAL','SIZE','SHIPPING','RETURNS'}

def finish_layout(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for old in soup.select('.photo-spacing,.text-photo-spacing'): old.decompose()
    # Remove empty generated headings/containers after their text has been omitted.
    for node in reversed(soup.find_all(['p','h1','h2','h3','h4','h5','h6','section','div'])):
        if not node.get_text(strip=True) and not node.find(['img','br']): node.decompose()
    def spacing(class_name):
        gap=soup.new_tag('div',attrs={'class':class_name,'style':'height:96px;line-height:24px;font-size:11px;margin:0;padding:0'})
        for _ in range(4):gap.append(soup.new_tag('br'))
        return gap
    for copy_node in soup.select('.operator-copy'):
        block=copy_node.find_parent('p') or copy_node
        if block.find_next('img'):
            block['style']=block.get('style','').rstrip(';')+';margin-bottom:0;padding-bottom:0;'
            block.insert_after(spacing('text-photo-spacing'))
    for photo in soup.find_all('img'):
        photo['style']=photo.get('style','').rstrip(';')+';display:block;margin:0 auto;'
        photo.insert_after(spacing('photo-spacing'))
    for node in soup.find_all(True):
        style=re.sub(r'(^|;)\s*font-size\s*:[^;]*','',node.get('style',''),flags=re.I)
        node['style']=style.rstrip(';')+';font-size:'+FONT_SIZE+';'
    return sanitize(str(soup))

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
    for id,value in replacements.items():
        if template.get('fixed_roles',{}).get(id) in OMITTED_DETAIL_ROLES or LABELS.get(str(value).strip().lower()) in OMITTED_DETAIL_ROLES:
            replacements[id]=''
    for slot in template['slots']:
        role=slot['role']
        if role in OMITTED_DETAIL_ROLES:
            replacements[slot['id']]=''; continue
        replacements[slot['id']]=values.get(role,'') if role not in used else ''
        if preview and not replacements[slot['id']] and role not in used: replacements[slot['id']]=LABEL.get(role,'확인할 내용')+' 입력 영역'
        used.add(role)
    description_ids={s['id'] for s in template['slots'] if s['role']=='DESCRIPTION'}
    def substitute(match):
        value=replacements.get(match[1],'')
        if match[1] in description_ids and value:
            return '<span class="operator-copy">'+format_text(value)+'</span>'
        return html.escape(str(value)).replace('\n','<br>')
    result=re.sub(r'\{\{(t\d+)\}\}',substitute,result)
    return finish_layout(result)

def compare(template,data,images):
    warnings=[]
    expected=Counter(i['type'] for i in template.get('images',[]))
    pools=image_pools(template,data,images)
    for role,count in expected.items():
        actual=len(pools.get(role,[]))
        if actual<count: warnings.append(f'{LABEL.get(role,"상품 사진")} 영역 {count}곳 중 {count-actual}곳이 비어 있습니다. 이대로 진행하면 빈 영역은 생략됩니다.')
    if template.get('unresolved'): warnings.append('기존 형식에 확인되지 않은 문구가 있습니다. 형식을 다시 분석해주세요.')
    return warnings
