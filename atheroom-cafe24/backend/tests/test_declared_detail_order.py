from bs4 import BeautifulSoup
from app.services.template_analysis_service import demo_sources
from app.services.html_parser_service import parse_html,compile_template
from app.services.render_service import render,compare
from app.api.templates import display_order

ORDER=['MAIN_CANDIDATE','DESCRIPTION','MATERIAL','SIZE','WEARING','PRODUCT','WEARING','PRODUCT','WEARING','DETAIL','SHIPPING','RETURNS']
def template():
    return compile_template([{'product_no':r['product_no'],'parsed':parse_html(r['description'],r['product_name'])} for r in demo_sources()[:3]])
def photos():
    # Deliberately unsorted across roles: role membership plus within-role order controls placement.
    roles=['PRODUCT','WEARING','DETAIL','WEARING','PRODUCT','WEARING','PRODUCT']
    ids=['product1','wear1','detail','wear2','product2','wear3','main']
    return [{'id':id,'file_url':f'https://new.example/{id}.jpg','image_type':role,'sort_order':i} for i,(id,role) in enumerate(zip(ids,roles))]
def test_declared_template_and_combined_information_section():
    t=template()
    assert t['section_order']==ORDER
    assert len(display_order(t))==10
    assert display_order(t)[1]=='상품 설명 · 소재 · 사이즈 안내'
    assert not t['unresolved']
def test_main_and_three_alternating_pairs_keep_exact_order():
    t=template()
    html=render(t,{'main_image_id':'main','description':'새 설명','material':'확인 소재','size':'확인 치수'},photos())
    soup=BeautifulSoup(html,'html.parser')
    assert [i['src'].rsplit('/',1)[1] for i in soup.find_all('img')]==['main.jpg','wear1.jpg','product1.jpg','wear2.jpg','product2.jpg','wear3.jpg','detail.jpg']
    info=soup.select_one('.product-information').get_text()
    assert '새 설명' in info and '확인 소재' in info and '확인 치수' in info
    assert html.index('main.jpg')<html.index('새 설명')<html.index('wear1.jpg')
    assert html.index('detail.jpg')<html.index('배송 안내')<html.index('교환/반품 안내')
    assert html.count('/main.jpg')==1
    assert 'example.com/' not in html and '기존 상품 소재' not in html

def test_missing_repeated_photo_is_reported():
    warnings=compare(template(),{'main_image_id':'main'},[p for p in photos() if p['id']!='wear3'])
    assert any('착용 사진 영역 3곳 중 1곳' in w for w in warnings)

def test_surplus_product_photo_stays_in_last_product_section():
    pics=photos()+[{'id':'extra','file_url':'https://new.example/extra.jpg','image_type':'PRODUCT','sort_order':20}]
    html=render(template(),{'main_image_id':'main'},pics)
    assert html.index('product2.jpg')<html.index('extra.jpg')<html.index('wear3.jpg')
