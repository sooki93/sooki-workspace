from fastapi import APIRouter,Depends,HTTPException,UploadFile,File,Response
from sqlalchemy import select
from app.db import get_db
from app.models import Product,ProductImage,uid
from app.security import current_user
from app.services.product_service import owned,editable,touch,images_for,refresh_preview
from app.services import image_service
from app.schemas.product import ImageOrder
router=APIRouter(prefix='/api')
@router.post('/products/{id}/images')
def upload(id:str,files:list[UploadFile]=File(...),user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p)
    previous=images_for(db,p)
    if not 1<=len(files)<=20 or len(files)+len(previous)>20: raise HTTPException(400,'사진은 최대 20장까지 올릴 수 있습니다.')
    created=[]
    try:
        for index,file in enumerate(files):
            raw=file.file.read(image_service.MAX_BYTES+1)
            converted,sha,phash=image_service.process_image(raw)
            image_id=uid(); key=f'{user.id}/{p.id}/{image_id}.jpg'; image_service.put(key,converted); created.append(key)
            im=ProductImage(id=image_id,product_id=p.id,file_url=f'/api/media/{image_id}',storage_key=key,file_hash=sha,perceptual_hash=phash,sort_order=len(previous)+index)
            db.add(im)
            if not p.main_image_id: p.main_image_id=image_id
        touch(p); db.flush(); refresh_preview(db,p); db.commit()
    except Exception as exc:
        db.rollback()
        for key in created: image_service.remove(key)
        if isinstance(exc,ValueError): raise HTTPException(400,str(exc)) from exc
        raise
    return {'ok':True}
@router.get('/media/{id}')
def media(id:str,user=Depends(current_user),db=Depends(get_db)):
    i=db.scalar(select(ProductImage).join(Product,Product.id==ProductImage.product_id).where(ProductImage.id==id,Product.user_id==user.id))
    if not i: raise HTTPException(404,'사진을 찾을 수 없습니다.')
    return Response(image_service.get(i.storage_key),media_type='image/jpeg')
@router.put('/products/{id}/images')
def reorder(id:str,body:ImageOrder,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p,body.revision); images=images_for(db,p); lookup={i.id:i for i in images}
    if set(lookup)!={i.id for i in body.images} or len(lookup)!=len(body.images) or body.main_image_id not in lookup: raise HTTPException(400,'사진 목록을 다시 확인해주세요.')
    for index,item in enumerate(body.images):
        i=lookup[item.id]; i.sort_order=index; i.image_type=item.image_type.value; i.confirmed=item.confirmed and item.image_type.value!='ETC'
    p.main_image_id=body.main_image_id; touch(p); db.flush(); refresh_preview(db,p); db.commit(); return {'ok':True}
@router.delete('/products/{id}/images/{image_id}')
def delete_image(id:str,image_id:str,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p)
    image=db.scalar(select(ProductImage).where(ProductImage.product_id==id,ProductImage.id==image_id))
    if not image: raise HTTPException(404,'사진을 찾을 수 없습니다.')
    key=image.storage_key; db.delete(image); db.flush()
    if p.main_image_id==image_id: p.main_image_id=next((i.id for i in images_for(db,p)),None)
    touch(p); refresh_preview(db,p); db.commit(); image_service.remove(key); return {'ok':True}
