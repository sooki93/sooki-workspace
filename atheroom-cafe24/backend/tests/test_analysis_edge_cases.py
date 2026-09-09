from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import User,BrandSettings
from app.services.template_analysis_service import build_profile,demo_sources

class PartialSource:
    mall='testmall'
    def __init__(self,*args): self.calls=[]
    def close(self): pass
    def recent(self,limit=30,offset=0):
        self.calls.append((limit,offset))
        return demo_sources() if offset==0 else []
    def detail(self,id):
        if id in (3000,2999,2998): raise ValueError('unreadable source')
        return next(r for r in demo_sources() if r['product_no']==id)
    def categories(self): return []

def test_partial_analysis_and_bounded_supplements(monkeypatch):
    monkeypatch.setattr('app.services.template_analysis_service.Cafe24Service',PartialSource)
    monkeypatch.setattr('app.services.template_analysis_service.analyze_source',lambda parsed,name:parsed)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine) as db:
        u=User(email='x@y');db.add(u);db.flush();db.add(BrandSettings(user_id=u.id));db.commit()
        p=build_profile(db,u.id)
        assert p.analysis['analyzed_product_count']==27
        assert p.analysis['failed_product_count']==3
        assert len(p.source_product_ids)==27 and 3000 not in p.source_product_ids
        assert p.status=='DRAFT' and p.global_template
