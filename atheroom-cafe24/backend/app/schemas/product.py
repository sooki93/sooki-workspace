from pydantic import BaseModel,ConfigDict,Field
from app.schemas.ai import Group,ImageType
class ProductEdit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int
    product_name: str = Field(max_length=250)
    price: int | None = Field(default=None,ge=0,le=2147483647)
    supply_price: int | None = Field(default=None,ge=0,le=2147483647)
    internal_product_group: Group
    cafe24_category_id: int | None = Field(default=None,ge=1)
    description: str = Field(max_length=5000)
    material: str = Field(default='',max_length=500)
    size: str = Field(default='',max_length=500)
    keywords: list[str] = Field(default_factory=list,max_length=50)
    main_image_id: str | None = None
    reference_product_id: str | None = None
    seo_title: str = Field(default='',max_length=250)
    seo_description: str = Field(default='',max_length=500)
class ImageEdit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: str
    image_type: ImageType
    confirmed: bool
class ImageOrder(BaseModel):
    revision: int
    images: list[ImageEdit]
    main_image_id: str
class Review(BaseModel):
    revision: int
    acknowledge_warnings: bool = False
class Publish(BaseModel):
    revision: int
    allow_duplicate: bool = False
