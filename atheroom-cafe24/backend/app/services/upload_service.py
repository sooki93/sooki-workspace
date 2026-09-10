from urllib.parse import urlparse
from app.models import Product, ProductImage
from app.services.cafe24_service import Cafe24Service,RemoteFailure
from app.services.product_service import images_for,data,image_dict
from app.services.render_service import render
from app.services.brief_description_service import brief_description
from app.services import image_service
from app.config import settings

class DemoCommerce:
    mall='demo'
    def close(self): pass
    def find_code(self,code): return []
    def create_product(self,payload): return {'product_no':int(payload['custom_product_code'][-6:],16)}
    def update_product(self,number,payload): return {'ok':True}
    def request(self,method,path,params=None,payload=None):
        if path=='/products/setting': return {'setting':{'calculate_price_based_on':'A'}}
        if path=='/products/images': return {'images':[{'path':'https://demo.invalid/example.jpg'}]}
        if method=='POST' and path.endswith('/images'):
            return {'image':{key:'https://demo.invalid/example.jpg' for key in ('detail_image','list_image','tiny_image','small_image')}}
        return {'ok':True}

def checkpoint(db,p,key,status,**extra):
    p.upload_steps={**p.upload_steps,key:{'status':status,**extra}}; db.commit()

def publish_product(db,p,service=None,demo=False):
    service=service or (DemoCommerce() if demo else Cafe24Service(db,p.user_id))
    pictures=images_for(db,p); failures=[]
    def step(key,fn,dependencies=True):
        saved=p.upload_steps.get(key,{})
        if saved.get('status')=='DONE': return saved.get('result')
        if not dependencies: return None
        checkpoint(db,p,key,'STARTED')
        try:
            result=fn(); checkpoint(db,p,key,'DONE',result=result); return result
        except Exception as exc:
            checkpoint(db,p,key,'UNKNOWN' if getattr(exc,'ambiguous',False) else 'FAILED',message='이 단계를 마치지 못했습니다.'); failures.append(key); return None
    try:
        if not p.cafe24_product_no:
            prior=p.upload_steps.get('create',{})
            code='ATR'+p.id.replace('-','')
            matches=[prior['result']] if prior.get('status')=='DONE' and prior.get('result',{}).get('product_no') else service.find_code(code)
            if len(matches)>1: raise RemoteFailure('같은 등록 기록이 여러 개 발견되었습니다. 쇼핑몰에서 확인해주세요.')
            if matches:
                p.cafe24_product_no=int(matches[0]['product_no']); checkpoint(db,p,'create','DONE',result={'product_no':p.cafe24_product_no})
            elif prior.get('status') in ('STARTED','UNKNOWN'):
                p.status='FAILED'; p.message='쇼핑몰의 등록 결과가 아직 확인되지 않습니다. 중복 방지를 위해 다시 만들지 않았습니다. 잠시 후 등록 결과를 다시 확인해주세요.'; db.commit(); return
            else:
                shop=service.request('GET','/products/setting').get('setting',{})
                if shop.get('calculate_price_based_on')=='B':
                    raise RemoteFailure('이 쇼핑몰은 세금 제외 금액으로 등록합니다. 운영 담당자가 금액 기준을 연결한 후 다시 진행해주세요.')
                payload={'product_name':p.product_name,'price':str(p.price),'supply_price':str(p.supply_price),'display':'F','selling':'F','has_option':'F','custom_product_code':code,'product_tag':p.keywords,'add_category_no':[{'category_no':p.cafe24_category_id,'recommend':'F','new':'F'}]}
                result=step('create',lambda:service.create_product(payload))
                if result:
                    p.cafe24_product_no=int(result['product_no']); db.commit()
                else:
                    p.status='FAILED';p.message='등록 결과를 확인하지 못했습니다. 다시 확인 버튼으로 진행 상황을 확인해주세요.'; db.commit(); return
        number=p.cafe24_product_no
        for im in pictures:
            def upload(im=im):
                response=service.request('POST','/products/images',payload={'requests':[{'image':image_service.encoded(im.storage_key)}]})
                path=response['images'][0]['path']
                if not isinstance(path,str) or not path: raise ValueError('missing uploaded path')
                return path
            step('image:'+im.id,upload)
        main=p.upload_steps.get('image:'+str(p.main_image_id),{})
        if main.get('status')=='DONE':
            def upload_main():
                im=next(im for im in pictures if im.id==p.main_image_id)
                response=service.request('POST',f'/products/{number}/images',payload={'shop_no':settings.cafe24_shop_no,'request':{'image_upload_type':'A','detail_image':'data:image/jpeg;base64,'+image_service.encoded(im.storage_key)}})
                # A 201 can still contain null image URLs when Cafe24 could not decode the input.
                if not all(response.get('image',{}).get(key) for key in ('detail_image','list_image','tiny_image','small_image')):
                    raise RemoteFailure('대표 사진이 저장되지 않았습니다. 다시 등록해주세요.')
                return response
            step('main',upload_main)
        additional=[im for im in pictures if im.id!=p.main_image_id]
        ready=all(p.upload_steps.get('image:'+im.id,{}).get('status')=='DONE' for im in additional)
        if additional and ready:
            # Replacement PUT avoids duplicate appends after a lost response. This is one retryable assignment step.
            step('additional',lambda:service.request('PUT',f'/products/{number}/additionalimages',payload={'shop_no':settings.cafe24_shop_no,'request':{'additional_image':[image_service.encoded(im.storage_key) for im in additional]}}))
        all_ready=all(p.upload_steps.get('image:'+im.id,{}).get('status')=='DONE' for im in pictures)
        if all_ready:
            uploaded=[]
            for im in pictures:
                url=p.upload_steps['image:'+im.id]['result']
                if url.startswith('//'): url='https:'+url
                elif url.startswith('/'): url=f'https://{service.mall}.cafe24.com'+url
                if urlparse(url).scheme!='https': raise ValueError('unsafe uploaded URL')
                uploaded.append({**image_dict(im),'file_url':url})
            rendered=render(p.template_snapshot,data(p),uploaded)
            step('description',lambda:service.update_product(number,{'description':rendered,'simple_description':brief_description(data(p)),'display':'F','selling':'F'}))
        step('seo',lambda:service.request('PUT',f'/products/{number}/seo',payload={'shop_no':settings.cafe24_shop_no,'request':{'meta_title':p.seo.get('title') or p.product_name,'meta_description':p.seo.get('description') or p.description,'meta_keywords':','.join(p.keywords),'meta_alt':p.product_name,'search_engine_exposure':'F'}}))
        required=['create','main','description','seo']+(['additional'] if additional else [])+['image:'+i.id for i in pictures]
        unfinished=[k for k in required if p.upload_steps.get(k,{}).get('status')!='DONE']
        p.status='PARTIAL_FAILED' if unfinished else 'UPLOADED'
        missing_images=sum(k.startswith('image:') for k in unfinished)
        p.message=(f'상품은 등록되었지만 이미지 {missing_images}장이 등록되지 않았습니다.' if missing_images else '상품은 등록되었지만 일부 정보를 마치지 못했습니다.') if unfinished else ('체험 등록이 완료되었습니다. 실제 쇼핑몰에는 전송되지 않았습니다.' if demo else '등록이 완료되었습니다. 현재 진열과 판매는 꺼져 있습니다.')
        db.commit()
    finally: service.close()
