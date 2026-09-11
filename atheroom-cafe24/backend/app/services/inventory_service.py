from app.config import settings
from app.services.cafe24_service import RemoteFailure


def disable_inventory(service,number):
    path=f'/products/{number}/variants'
    variants=service.request('GET',path).get('variants',[])
    if not variants or any(not v.get('variant_code') for v in variants):
        raise RemoteFailure('상품 품목을 확인하지 못했습니다. 다시 확인해주세요.')
    for variant in variants:
        if variant.get('use_inventory')!='F':
            response=service.request('PUT',f"{path}/{variant['variant_code']}",payload={
                'shop_no':settings.cafe24_shop_no,'request':{'use_inventory':'F'}})
            # The list endpoint may still return cached inventory after a successful update.
            saved=response.get('variant',{})
            if saved.get('variant_code')!=variant['variant_code'] or saved.get('inventories',{}).get('use_inventory')!='F':
                raise RemoteFailure('재고관리 사용안함 설정을 확인하지 못했습니다. 다시 확인해주세요.',ambiguous=True)
    return {'variant_codes':[v['variant_code'] for v in variants],'use_inventory':'F'}
