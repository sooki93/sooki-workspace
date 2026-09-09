import pytest
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import Base
from app.models import User,TemplateProfile
from app.services.template_analysis_service import build_profile
from app.api.templates import activate

def test_analysis_is_draft_and_activation_archives():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(email='test@example.com'); db.add(user); db.commit()
        first=build_profile(db,user.id,demo=True)
        assert first.status=='DRAFT' and first.analysis['analyzed_product_count']==30
        assert first.global_template and len(first.category_templates)==7
        activate(first.id,user,db)
        second=build_profile(db,user.id,demo=True)
        assert first.status=='ACTIVE' and second.status=='DRAFT'
        activate(second.id,user,db)
        assert first.status=='ARCHIVED' and second.status=='ACTIVE'
        assert db.scalars(select(TemplateProfile).where(TemplateProfile.status=='ACTIVE')).all()==[second]

def test_database_rejects_two_active():
    engine=create_engine('sqlite://'); Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(email='x@y.com'); db.add(user); db.flush()
        db.add_all([TemplateProfile(user_id=user.id,mall_id='x',version=i,status='ACTIVE') for i in (1,2)])
        with pytest.raises(IntegrityError): db.commit()
