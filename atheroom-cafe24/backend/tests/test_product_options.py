import pytest
from app.schemas.product import OptionSettings
from app.services.option_service import option_payload,ensure_options,option_errors
from app.services.cafe24_service import RemoteFailure
from app.services.upload_service import DemoCommerce,publish_product
from test_phase6 import fixture
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base

CONFIG={'enabled':True,'color_values':'SILVER, gold, silver','size_values':'FREE'}

def test_direct_options_use_uppercase_names_and_unique_lowercase_values():
    config=OptionSettings.model_validate(CONFIG).model_dump()
    assert config['color_values']=='silver, gold, silver'
    payload=option_payload(config)
    assert payload['option_type']=='T' and payload['option_list_type']=='S'
    assert [(o['option_name'],o['option_value']) for o in payload['options']]==[
        ('COLOR',[{'option_text':'silver'},{'option_text':'gold'}]),('SIZE',[{'option_text':'free'}])]
    assert option_errors({'enabled':True})
    assert not option_errors({'enabled':False})

def test_unknown_post_reconciles_without_recreating_or_deleting_options():
    class LostResponse(DemoCommerce):
        posts=0
        def request(self,method,path,params=None,payload=None):
            result=super().request(method,path,params,payload)
            if method=='POST':
                self.posts+=1
                raise RemoteFailure(ambiguous=True)
            return result
    service=LostResponse()
    with pytest.raises(RemoteFailure):ensure_options(service,123,CONFIG)
    assert ensure_options(service,123,CONFIG,'UNKNOWN')=={'confirmed':True}
    assert service.posts==1
    with pytest.raises(RemoteFailure):ensure_options(service,123,{**CONFIG,'size_values':'s'})
    assert service.posts==1
    with pytest.raises(RemoteFailure) as error:ensure_options(DemoCommerce(),123,CONFIG,'UNKNOWN')
    assert error.value.ambiguous

def test_registration_includes_options_and_retries_only_unfinished(monkeypatch):
    monkeypatch.setattr('app.services.image_service.encoded',lambda key:'encoded')
    class BrokenOnce(DemoCommerce):
        fail=True
        posts=0
        def request(self,method,path,params=None,payload=None):
            if path.endswith('/options') and method=='POST':
                self.posts+=1
                if self.fail:
                    self.fail=False
                    raise RemoteFailure()
            return super().request(method,path,params,payload)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        p=fixture(db);p.option_settings=CONFIG;db.commit();service=BrokenOnce()
        publish_product(db,p,service);assert p.status=='PARTIAL_FAILED'
        publish_product(db,p,service);assert p.status=='UPLOADED'
        assert p.upload_steps['options']['status']=='DONE' and service.posts==2
