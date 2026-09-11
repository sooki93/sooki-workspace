import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, DateTime, Boolean, ForeignKey, JSON, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)
J = JSON().with_variant(JSONB, 'postgresql')
class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(default='ADMIN')
class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
class OAuthState(Base):
    __tablename__ = 'oauth_states'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    session_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
class Cafe24Account(Base):
    __tablename__ = 'cafe24_accounts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), unique=True)
    mall_id: Mapped[str] = mapped_column(String(64), unique=True)
    access_token: Mapped[str] = mapped_column(Text, default='')
    refresh_token: Mapped[str] = mapped_column(Text, default='')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
class BrandSettings(Base):
    __tablename__ = 'brand_settings'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    rules: Mapped[dict] = mapped_column(J, default=dict)
    category_mapping: Mapped[dict] = mapped_column(J, default=dict)
    categories: Mapped[list] = mapped_column(J, default=list)
class TemplateProfile(Base):
    __tablename__ = 'template_profiles'
    __table_args__ = (UniqueConstraint('user_id', 'version'), Index('one_active_profile', 'user_id', unique=True, postgresql_where=text("status = 'ACTIVE'"), sqlite_where=text("status = 'ACTIVE'")))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    mall_id: Mapped[str] = mapped_column(String(64))
    brand: Mapped[str] = mapped_column(default='attheroom')
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(default='DRAFT')
    analysis: Mapped[dict] = mapped_column(J, default=dict)
    source_product_ids: Mapped[list] = mapped_column(J, default=list)
    global_template: Mapped[dict] = mapped_column(J, default=dict)
    category_templates: Mapped[dict] = mapped_column(J, default=dict)
    styles: Mapped[dict] = mapped_column(J, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
class SourceProduct(Base):
    __tablename__ = 'source_products'
    __table_args__ = (UniqueConstraint('user_id', 'product_no'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    product_no: Mapped[int] = mapped_column(Integer)
    product_name: Mapped[str] = mapped_column(Text)
    product_group: Mapped[str] = mapped_column(default='ETC')
    created_date: Mapped[str] = mapped_column(String(64))
    thumbnail: Mapped[str] = mapped_column(Text, default='')
    parsed: Mapped[dict] = mapped_column(J, default=dict)
    image_hashes: Mapped[list] = mapped_column(J, default=list)
class Product(Base):
    __tablename__ = 'products'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    cafe24_product_no: Mapped[int | None] = mapped_column(Integer)
    brand: Mapped[str] = mapped_column(default='attheroom')
    internal_product_group: Mapped[str] = mapped_column(default='ETC')
    cafe24_category_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(default='DRAFT')
    revision: Mapped[int] = mapped_column(default=1)
    reviewed_revision: Mapped[int | None] = mapped_column(Integer)
    template_profile_id: Mapped[str | None] = mapped_column(ForeignKey('template_profiles.id'))
    template_snapshot: Mapped[dict] = mapped_column(J, default=dict)
    product_name: Mapped[str] = mapped_column(Text, default='')
    price: Mapped[int | None] = mapped_column(Integer)
    supply_price: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text, default='')
    material: Mapped[str] = mapped_column(Text, default='')
    size: Mapped[str] = mapped_column(Text, default='')
    option_settings: Mapped[dict] = mapped_column(J, default=dict, server_default='{}')
    keywords: Mapped[list] = mapped_column(J, default=list)
    seo: Mapped[dict] = mapped_column(J, default=dict)
    ai_result: Mapped[dict] = mapped_column(J, default=dict)
    reference_product_id: Mapped[str | None] = mapped_column(String(36))
    main_image_id: Mapped[str | None] = mapped_column(String(36))
    rendered_html: Mapped[str] = mapped_column(Text, default='')
    warnings: Mapped[list] = mapped_column(J, default=list)
    upload_steps: Mapped[dict] = mapped_column(J, default=dict)
    message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
class ProductImage(Base):
    __tablename__ = 'product_images'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'), index=True)
    file_url: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    perceptual_hash: Mapped[str] = mapped_column(String(64))
    image_type: Mapped[str] = mapped_column(default='ETC')
    ai_confidence: Mapped[float] = mapped_column(Float, default=0)
    confirmed: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(Integer)
class AIGeneration(Base):
    __tablename__ = 'ai_generations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    product_id: Mapped[str] = mapped_column(ForeignKey('products.id'))
    input: Mapped[dict] = mapped_column(J)
    output: Mapped[dict] = mapped_column(J)
    model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Job(Base):
    __tablename__ = 'jobs'
    __table_args__ = (Index('one_pending_job', 'user_id', 'kind', 'target_id', unique=True, postgresql_where=text("status IN ('QUEUED', 'RUNNING')"), sqlite_where=text("status IN ('QUEUED', 'RUNNING')")),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(36), default='mall')
    status: Mapped[str] = mapped_column(default='QUEUED')
    message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
