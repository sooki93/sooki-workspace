import re
from app.config import settings
from app.services.cafe24_service import RemoteFailure

def values(text):
    return list(dict.fromkeys(v.strip().lower() for v in re.split(r'[,\n]',text) if v.strip()))

def option_errors(config):
    if not config or not config.get('enabled'): return []
    errors=[]
    for key,label in [('color_values','COLOR'),('size_values','SIZE')]:
        items=values(config.get(key,''))
        if not items:errors.append((key,f'{label} 옵션 값을 입력해주세요.'))
        elif len(items)>30 or any(len(v)>30 for v in items):errors.append((key,f'{label} 옵션은 값마다 30자 이내, 최대 30개로 입력해주세요.'))
    if len(values(config.get('color_values','')))*len(values(config.get('size_values','')))>100:
        errors.append(('size_values','색상과 사이즈의 조합은 최대 100개까지 입력해주세요.'))
    return errors

def option_payload(config):
    errors=option_errors(config)
    if errors:raise ValueError(' '.join(message for _,message in errors))
    return {'has_option':'T','option_type':'T','option_list_type':'S','options':[
        {'option_name':label,'option_value':[{'option_text':v} for v in values(config[key])],'option_display_type':'S'}
        for key,label in [('color_values','COLOR'),('size_values','SIZE')]]}

def signature(options):
    return [(o.get('option_name'),[v.get('option_text') for v in o.get('option_value',[])]) for o in options]

def ensure_options(service,number,config,prior_status=None):
    desired=option_payload(config)
    current=service.request('GET',f'/products/{number}/options').get('option',{})
    if current.get('has_option')=='T':
        if signature(current.get('options',[]))==signature(desired['options']) and current.get('option_type')=='T':
            return {'confirmed':True}
        raise RemoteFailure('기존 옵션이 입력한 값과 다릅니다. 쇼핑몰의 옵션을 확인해주세요.')
    if prior_status in ('STARTED','UNKNOWN'):
        raise RemoteFailure('이전 옵션 저장 결과가 아직 확인되지 않습니다. 잠시 후 다시 확인해주세요.',ambiguous=True)
    response=service.request('POST',f'/products/{number}/options',payload={'shop_no':settings.cafe24_shop_no,'request':desired})
    saved=response.get('option',{})
    if saved.get('has_option')!='T' or signature(saved.get('options',[]))!=signature(desired['options']):
        raise RemoteFailure('옵션 저장 결과를 다시 확인해주세요.',ambiguous=True)
    return {'confirmed':True}
