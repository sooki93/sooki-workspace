from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Group(str,Enum):
    RING='RING'; NECKLACE='NECKLACE'; EARRING='EARRING'; BRACELET='BRACELET'; PIERCING='PIERCING'; HAIR='HAIR'; ETC='ETC'
class ImageType(str,Enum):
    MAIN_CANDIDATE='MAIN_CANDIDATE'; WEARING='WEARING'; PRODUCT='PRODUCT'; DETAIL='DETAIL'; SIZE_REFERENCE='SIZE_REFERENCE'; ETC='ETC'
class Role(str,Enum):
    NAME='NAME'; DESCRIPTION='DESCRIPTION'; SIZE='SIZE'; MATERIAL='MATERIAL'; NOTICE='NOTICE'; SHIPPING='SHIPPING'; RETURNS='RETURNS'; AS='AS'; BRAND='BRAND'; LABEL='LABEL'; UNKNOWN='UNKNOWN'
class GroupGuess(Strict):
    value: Group
    confidence: float = Field(ge=0,le=1)
class ImageGuess(Strict):
    id: str
    type: ImageType
    confidence: float = Field(ge=0,le=1)
class ProductAnalysis(Strict):
    product_group: GroupGuess
    product_name: str = Field(max_length=250)
    description: str = Field(max_length=5000)
    category_recommendation: GroupGuess
    search_keywords: list[str]
    seo_title: str
    seo_description: str
    images: list[ImageGuess]
    missing_fields: list[str]
class SemanticSlot(Strict):
    id: str
    role: Role
class SemanticImage(Strict):
    id: str
    type: ImageType
class SourceAnalysis(Strict):
    product_group: GroupGuess
    slots: list[SemanticSlot]
    images: list[SemanticImage]
    product_name_rules: str
    description_rules: str
