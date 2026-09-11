import pytest
from app.services.inventory_service import disable_inventory
from app.services.cafe24_service import RemoteFailure


class InventoryShop:
    def __init__(self):
        self.variants=[{'variant_code':'P00000000001','use_inventory':'T'}, {'variant_code':'P00000000002','use_inventory':'F'}]
        self.writes=[]
        self.save=True

    def request(self,method,path,params=None,payload=None):
        if method=='GET':return {'variants':self.variants}
        self.writes.append((path,payload))
        if self.save:self.variants[0]['use_inventory']='F'
        return {'variant':{'variant_code':self.variants[0]['variant_code'],'inventories':{'use_inventory':self.variants[0]['use_inventory']}}}


def test_disables_all_variants_without_changing_quantity_or_sale_settings():
    shop=InventoryShop()
    assert disable_inventory(shop,123)['use_inventory']=='F'
    assert shop.writes==[('/products/123/variants/P00000000001',{'shop_no':1,'request':{'use_inventory':'F'}})]
    disable_inventory(shop,123)
    assert len(shop.writes)==1


def test_unconfirmed_inventory_is_not_reported_as_complete():
    shop=InventoryShop();shop.save=False
    with pytest.raises(RemoteFailure):disable_inventory(shop,123)
    shop.variants=[]
    with pytest.raises(RemoteFailure):disable_inventory(shop,123)
