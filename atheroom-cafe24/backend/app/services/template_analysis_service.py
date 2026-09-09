from datetime import datetime,timezone,timedelta
import logging
from collections import Counter
from sqlalchemy import select,func
from app.models import TemplateProfile,SourceProduct,User,BrandSettings
from app.services.html_parser_service import parse_html,compile_template,infer_group
from app.services.style_clustering_service import cluster,select_stable
from app.services.openai_service import analyze_source
from app.services.cafe24_service import Cafe24Service
from app.config import settings

def creation_time(row):
    value=datetime.fromisoformat(row['created_date'].replace('Z','+00:00'))
    return value if value.tzinfo else value.replace(tzinfo=timezone(timedelta(hours=9)))

GROUPS=['RING','NECKLACE','EARRING','BRACELET','PIERCING','HAIR','ETC']
def demo_sources():
    rows=[]
    for i in range(30):
        group=GROUPS[i%7]; name={'RING':'반지','NECKLACE':'목걸이','EARRING':'귀걸이','BRACELET':'팔찌','PIERCING':'피어싱','HAIR':'헤어핀','ETC':'기타 장신구'}[group]
        html=(
            '<div class="attheroom-detail" style="max-width:780px;margin:0 auto;text-align:center;color:#252525">'
            f'<div class="main-photo"><img class="main-photo" src="https://example.com/main-{i}.jpg" style="width:100%"/></div>'
            '<section class="product-information">'
            f'<p style="font-size:16px;line-height:1.8">구조와 디테일을 중심으로 소개하는 {name} 설명 {i}입니다.</p>'
            f'<h3>MATERIAL</h3><p>기존 상품 소재 {i}</p><h3>SIZE</h3><p>{i+1}cm</p>'
            '</section>'
            f'<div class="wearing"><img class="wearing" src="https://example.com/wear-a-{i}.jpg" style="width:100%"/></div>'
            f'<div class="product"><img src="https://example.com/product-a-{i}.jpg" style="width:100%"/></div>'
            f'<div class="wearing"><img class="wearing" src="https://example.com/wear-b-{i}.jpg" style="width:100%"/></div>'
            f'<div class="product"><img src="https://example.com/product-b-{i}.jpg" style="width:100%"/></div>'
            f'<div class="wearing"><img class="wearing" src="https://example.com/wear-c-{i}.jpg" style="width:100%"/></div>'
            f'<div class="detail"><img class="closeup" src="https://example.com/detail-{i}.jpg" style="width:100%"/></div>'
            '<section class="shipping"><h3>배송 안내</h3><p>체험용 배송 안내 영역입니다. 실제 배송 조건은 쇼핑몰의 안내를 사용합니다.</p></section>'
            '<section class="returns"><h3>교환/반품 안내</h3><p>체험용 교환·반품 안내 영역입니다. 실제 정책은 쇼핑몰의 안내를 사용합니다.</p></section>'
            '</div>'
        )
        rows.append({'product_no':3000-i,'product_name':f'체험 {name} {i+1:02d}','created_date':f'2026-08-{30-i:02d}T12:00:00+09:00','description':html,'detail_image':'','group':group})
    return rows

def build_profile(db,user_id,demo=False):
    service=None if demo else Cafe24Service(db,user_id)
    try:
        candidates=demo_sources() if demo else service.recent(30)
        # No replacement by older products when a member of the recent 30 fails.
        candidates=sorted(candidates,key=creation_time,reverse=True)[:30]
        successful=[]; failed=0; extra_count=0; extra_failed=0
        def analyze(row):
            detail=row if demo else service.detail(row['product_no'])
            parsed=parse_html(detail.get('description') or '',detail['product_name'])
            if demo: parsed['group']=row['group']
            else: parsed=analyze_source(parsed,detail['product_name'])
            record=db.scalar(select(SourceProduct).where(SourceProduct.user_id==user_id,SourceProduct.product_no==row['product_no']))
            if not record: record=SourceProduct(user_id=user_id,product_no=row['product_no']); db.add(record)
            record.product_name=detail['product_name']; record.created_date=detail['created_date']; record.thumbnail=detail.get('detail_image') or ''; record.product_group=parsed['group']; record.parsed=parsed
            db.commit()
            return {'product_no':record.product_no,'parsed':parsed,'created_date':record.created_date}
        for row in candidates:
            try: successful.append(analyze(row))
            except Exception as exc:
                db.rollback(); failed+=1; logging.warning('source_analysis_failed product=%s type=%s',row['product_no'],type(exc).__name__)
        category_samples={g:[s for s in successful if s['parsed']['group']==g] for g in GROUPS}
        sparse={g for g,s in category_samples.items() if len(s)<3}
        # At most 50 older products total. Only matching sparse groups receive detail fetch/HTML analysis.
        if sparse and service:
            older=service.recent(50,offset=len(candidates))
            seen={r['product_no'] for r in candidates}
            for row in older[:50]:
                if row['product_no'] in seen: continue
                group=infer_group(row['product_name'])
                if group not in sparse or len(category_samples[group])>=5: continue
                try:
                    sample=analyze(row); actual=sample['parsed']['group']
                    if actual in sparse and len(category_samples[actual])<5:
                        category_samples[actual].append(sample); extra_count+=1
                except Exception as exc:
                    db.rollback(); extra_failed+=1; logging.warning('supplement_failed type=%s',type(exc).__name__)
        styles={}; global_template={}; categories={}
        def build(scope,samples):
            groups=cluster(samples); chosen=select_stable(groups)
            for g in groups:
                styles[scope+'_'+g['id']]={k:v for k,v in g.items() if k!='samples'} | {'source_product_ids':[s['product_no'] for s in g['samples']]}
            if not chosen: return {}
            compiled=compile_template(chosen['samples']); compiled['active_style_id']=scope+'_'+chosen['id']
            return compiled
        global_template=build('GLOBAL',successful)
        for group,samples in category_samples.items():
            if len(samples)>=3:
                result=build(group,sorted(samples,key=lambda s:s['created_date'],reverse=True))
                if result: categories[group]=result
        if service:
            brand=db.get(BrandSettings,user_id)
            brand.categories=[{'id':int(c['category_no']),'name':c['category_name']} for c in service.categories()]
            db.commit()
        db.scalar(select(User).where(User.id==user_id).with_for_update())
        version=(db.scalar(select(func.max(TemplateProfile.version)).where(TemplateProfile.user_id==user_id)) or 0)+1
        profile=TemplateProfile(user_id=user_id,mall_id='demo' if demo else service.mall,version=version,analysis={'requested_product_count':30,'received_product_count':len(candidates),'analyzed_product_count':len(successful),'failed_product_count':failed,'supplemental_product_count':extra_count,'supplemental_failed_count':extra_failed,'stable':bool(global_template)},source_product_ids=[s['product_no'] for s in successful],global_template=global_template,category_templates=categories,styles=styles)
        db.add(profile); db.commit()
        logging.info('analysis_summary success=%d failed=%d extra=%d',len(successful),failed,extra_count)
        return profile
    finally:
        if service: service.close()
