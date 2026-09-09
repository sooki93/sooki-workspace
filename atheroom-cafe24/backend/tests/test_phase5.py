from app.services.html_parser_service import parse_html,compile_template
from app.services.render_service import render,compare

def template():
    return compile_template([{'product_no':i,'parsed':parse_html('<div class="keep" style="text-align:center"><p>기존 고유 설명</p><img src="https://old.example/image.jpg"><h3>SIZE</h3><p>123cm</p><h3>MATERIAL</h3><p>기존 소재</p><h3>NOTICE</h3><p>공통 구매 안내</p></div>')} for i in range(3)])
def test_render_preserves_structure_and_prevents_source_leak():
    t=template(); result=render(t,{'description':'새 상품 설명 <script>bad</script>','size':'5cm','material':'확인된 소재'},[{'file_url':'https://new.example/1.jpg','image_type':'PRODUCT'},{'file_url':'https://new.example/2.jpg','image_type':'PRODUCT'}])
    assert 'class="keep"' in result and '공통 구매 안내' in result
    assert '기존 고유 설명' not in result and '123cm' not in result and 'old.example' not in result
    assert '<script>' not in result and result.count('<img')==2
    assert result.index('SIZE')<result.index('MATERIAL')<result.index('NOTICE')
def test_single_pass_interpolation():
    result=render(template(),{'description':'{{t4}}','size':'new size','material':'new material'},[])
    assert '{{t4}}' in result
