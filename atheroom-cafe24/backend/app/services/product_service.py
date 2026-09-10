import copy
from sqlalchemy import select
from fastapi import HTTPException
from app.models import Product,ProductImage,TemplateProfile,BrandSettings,AIGeneration,SourceProduct
from app.services import image_service
from app.services.openai_service import analyze_product
from app.services.html_parser_service import compile_template
from app.services.render_service import render,compare,image_pools
from app.schemas.ai import ProductAnalysis
from app.config import settings

LOCKED={'AI_GENERATING','UPLOADING','UPLOADED','PARTIAL_FAILED'}
def owned(db,user_id,id,lock=False):
    stmt=select(Product).where(Product.id==id,Product.user_id==user_id)
    p=db.scalar(stmt.with_for_update() if lock else stmt)
    if not p: raise HTTPException(404,'상품을 찾을 수 없습니다.')
    return p
def images_for(db,p): return list(db.scalars(select(ProductImage).where(ProductImage.product_id==p.id).order_by(ProductImage.sort_order)))
def image_dict(i): return {k:getattr(i,k) for k in ('id','file_url','image_type','ai_confidence','confirmed','sort_order')}
def data(p): return {k:getattr(p,k) for k in ('product_name','description','material','size','main_image_id')}
def editable(p,revision=None):
    if p.status in LOCKED or p.cafe24_product_no: raise HTTPException(409,'현재 상품은 수정할 수 없습니다. 진행 중인 작업을 확인해주세요.')
    if revision is not None and p.revision!=revision: raise HTTPException(409,'다른 화면에서 변경되었습니다. 새로고침 후 다시 시도해주세요.')
def touch(p):
    p.revision+=1; p.reviewed_revision=None
    p.status='DRAFT' if not p.template_profile_id else 'AI_GENERATED'
def choose_template(db,p):
    profile=db.scalar(select(TemplateProfile).where(TemplateProfile.user_id==p.user_id,TemplateProfile.status=='ACTIVE'))
    if not profile: raise HTTPException(400,'관리자 화면에서 기존 상품 형식을 확인하고 사용을 승인해주세요.')
    selected=copy.deepcopy(profile.category_templates.get(p.internal_product_group) or profile.global_template)
    if p.reference_product_id:
        reference=db.scalar(select(SourceProduct).where(SourceProduct.id==p.reference_product_id,SourceProduct.user_id==p.user_id))
        if not reference: raise HTTPException(400,'참고 상품을 다시 선택해주세요.')
        # Compile single product structure, borrowing only proven fixed text from active profile.
        selected=compile_template([{'product_no':reference.product_no,'parsed':reference.parsed}])
        proven=set(profile.global_template.get('fixed_blocks',{}).values())
        for category in profile.category_templates.values(): proven.update(category.get('fixed_blocks',{}).values())
        for slot in reference.parsed['slots']:
            if slot['role'] in ('NOTICE','SHIPPING','RETURNS','AS','BRAND','LABEL') and slot['text'] in proven:
                selected['fixed_blocks'][slot['id']]=slot['text']
                selected['slots']=[s for s in selected['slots'] if s['id']!=slot['id']]
                selected['unresolved']=[s for s in selected['unresolved'] if s!=slot['id']]
    if selected.get('unresolved'): raise HTTPException(400,'이 형식에는 확인이 필요한 공통 문구가 있습니다. 다른 형식을 선택해주세요.')
    brand=db.get(BrandSettings,p.user_id)
    if brand.rules.get('fixed_notice'):
        targets=[id for id,role in selected.get('fixed_roles',{}).items() if role=='NOTICE']
        if not targets: raise HTTPException(400,'현재 형식에 구매 안내 영역이 없습니다. 안내 영역이 있는 형식을 먼저 승인해주세요.')
        for index,id in enumerate(targets): selected['fixed_blocks'][id]=brand.rules['fixed_notice'] if index==0 else ''
    p.template_profile_id=profile.id; p.template_snapshot=selected
    return profile

def current_warnings(db,p):
    return compare(p.template_snapshot,data(p),[image_dict(i) for i in images_for(db,p)]) if p.template_snapshot else []

def refresh_preview(db,p):
    if not p.template_snapshot: return
    images=[image_dict(i) for i in images_for(db,p)]
    p.rendered_html=render(p.template_snapshot,data(p),images)
    p.warnings=compare(p.template_snapshot,data(p),images)

def review_issues(db,p):
    issues=[]; brand=db.get(BrandSettings,p.user_id)
    def add(code,message,target='product-information',image_id=None):
        issues.append({'code':code,'message':message,'target':target,'image_id':image_id})
    if not p.product_name.strip(): add('name','상품명을 입력해주세요.','field-product-name')
    if p.price is None: add('price','판매가를 입력해주세요.','field-price')
    if p.supply_price is None: add('supply_price','공급가를 입력해주세요.','field-supply-price')
    if not p.cafe24_category_id: add('category','쇼핑몰 카테고리를 선택해주세요.','field-category')
    elif p.cafe24_category_id not in {c['id'] for c in brand.categories}: add('category','쇼핑몰 카테고리를 다시 선택해주세요.','field-category')
    images=images_for(db,p)
    if not images or p.main_image_id not in {i.id for i in images}: add('main_image','맨 앞에 사용할 대표 사진을 지정해주세요.','product-photos')
    expected={i['type'] for i in p.template_snapshot.get('images',[])}
    image_labels={'WEARING':'착용 사진','PRODUCT':'제품 사진','DETAIL':'디테일 사진','SIZE_REFERENCE':'사이즈 참고 사진','MAIN_CANDIDATE':'대표 이미지 후보','ETC':'미분류'}
    for index,i in enumerate(images):
        if i.id==p.main_image_id and 'MAIN_CANDIDATE' in expected: continue
        role='PRODUCT' if i.image_type=='MAIN_CANDIDATE' else i.image_type
        if i.image_type=='ETC':
            add('image_unclassified',f'사진 {index+1}: 아직 미분류입니다. 사진 아래에서 용도를 선택해주세요.','photo-'+i.id,i.id)
        elif expected and role not in expected:
            add('image_unsupported',f'사진 {index+1}: “{image_labels.get(i.image_type,"현재 용도")}”를 배치할 곳이 없습니다. 사진 아래에서 사용할 용도를 다시 선택해주세요.','photo-'+i.id,i.id)
        elif not i.confirmed:
            add('image_unconfirmed',f'사진 {index+1}: 제안된 용도가 맞는지 확인하고 “이 용도로 확인”을 눌러주세요.','photo-'+i.id,i.id)
    if p.ai_result.get('product_group',{}).get('confidence',1)<.85 and not p.ai_result.get('group_confirmed'):
        add('group_unconfirmed','선택한 상품군을 확인한 뒤 “이 상품군으로 확인하고 저장”을 눌러주세요.','field-group')
    if brand.rules.get('require_material') and not p.material.strip(): add('material','소재를 입력해주세요.','field-material')
    if brand.rules.get('require_size') and not p.size.strip(): add('size','사이즈를 입력해주세요.','field-size')
    # Operator-authored copy is not a source of inferred facts or registration blockers.
    # Writing preferences guide AI generation; required facts use their dedicated fields.
    if not p.template_snapshot: add('template','사진을 올린 뒤 초안을 만들어 상품 형식을 적용해주세요.','product-photos')
    return issues

def missing(db,p):
    return [issue['message'] for issue in review_issues(db,p)]

def allowed_image_types(p):
    return [role for role in ('WEARING','PRODUCT','DETAIL','SIZE_REFERENCE','ETC') if role in {i['type'] for i in p.template_snapshot.get('images',[])}] if p.template_snapshot else ['WEARING','PRODUCT','DETAIL','SIZE_REFERENCE']

def generate(db,p,demo=False):
    images=images_for(db,p)
    if not images: raise ValueError('먼저 상품 사진을 올려주세요.')
    brand=db.get(BrandSettings,p.user_id)
    group_confirmed=bool(p.ai_result.get('group_confirmed'))
    selected_group=p.internal_product_group
    preserve_image_order=any(i.confirmed for i in images)
    inputs=[{'id':i.id,'url':image_service.data_url(i.storage_key)} for i in images]
    if demo:
        output=ProductAnalysis.model_validate({'product_group':{'value':p.internal_product_group,'confidence':.5},'product_name':'직접 확인할 상품명','description':'사진을 확인하고 제품의 구조와 특징을 입력해주세요.','category_recommendation':{'value':p.internal_product_group,'confidence':.5},'search_keywords':[],'seo_title':'','seo_description':'','images':[{'id':i.id,'type':'PRODUCT','confidence':0} for i in images],'missing_fields':['price','supply_price','material','size']}).model_dump(mode='json')
    else: output=analyze_product(p,inputs,brand.rules)
    p.internal_product_group=selected_group if group_confirmed else output['product_group']['value']
    choose_template(db,p)
    if not demo:
        # Second pass writes with the now-selected saved category style; never re-fetches source products.
        output=analyze_product(p,inputs,brand.rules,{'product_name_rules':p.template_snapshot['product_name_rules'],'description_rules':p.template_snapshot['description_rules'],'image_rules':p.template_snapshot['image_rules']})
        if output['product_group']['value']!=p.internal_product_group:
            output['product_group']={'value':p.internal_product_group,'confidence':0.5}
    guesses={i['id']:i for i in output['images']}
    if set(guesses)!={i.id for i in images} or len(output['images'])!=len(images): raise ValueError('사진 분류를 다시 시도해주세요.')
    for i in images:
        guess=guesses[i.id]
        if not i.confirmed:
            i.image_type=guess['type'] if guess['confidence']>=.6 else 'ETC'; i.ai_confidence=guess['confidence']; i.confirmed=guess['confidence']>=.85
    manual=set(p.ai_result.get('manual_fields',[]))
    # Older drafts have no field markers: preserve text that differs from their last AI result.
    if 'manual_fields' not in p.ai_result:
        for field,output_key in (('product_name','product_name'),('description','description'),('keywords','search_keywords')):
            if getattr(p,field) and getattr(p,field)!=p.ai_result.get(output_key): manual.add(field)
        for field in ('title','description'):
            if p.seo.get(field) and p.seo[field]!=p.ai_result.get('seo_'+field): manual.add('seo_'+field)
    for field,output_key in (('product_name','product_name'),('description','description'),('keywords','search_keywords')):
        if field not in manual: setattr(p,field,output[output_key])
    p.seo={field:p.seo.get(field,'') if 'seo_'+field in manual else output['seo_'+field] for field in ('title','description')}
    p.ai_result={**output,'group_confirmed':group_confirmed,'manual_fields':sorted(manual)}
    if not group_confirmed: p.cafe24_category_id=brand.category_mapping.get(p.internal_product_group)
    if not preserve_image_order:
        for order,guess in enumerate(output['images']):
            next(i for i in images if i.id==guess['id']).sort_order=order
    p.revision+=1; p.reviewed_revision=None
    db.add(AIGeneration(product_id=p.id,input={'image_ids':[i.id for i in images],'user_facts':{'material':p.material,'size':p.size},'template_profile_id':p.template_profile_id},output=output,model='demo-no-ai' if demo else settings.openai_model))
    refresh_preview(db,p); p.status='NEEDS_INPUT' if missing(db,p) else 'AI_GENERATED'; db.commit()
