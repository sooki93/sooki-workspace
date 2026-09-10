import pytest
from bs4 import BeautifulSoup
from app.services.brief_description_service import brief_description,SIZE_NOTICE,COLOR_NOTICE,SILVER_NOTICE

def text(data):
    return BeautifulSoup(brief_description(data),'html.parser').get_text('\n')

def test_product_specific_detail_info_and_fixed_notices():
    data={'description':'comment\n멋진 목걸이\ndetail info\nmaterial 신주, 무니켈도금\ncolor silver\nsize 총 체인 길이 약 60cm\n\n'+COLOR_NOTICE,'material':'신주','size':'free'}
    assert text(data)=='\n'.join(['detail info','material 신주, 무니켈도금','color silver','size 총 체인 길이 약 60cm',SIZE_NOTICE,COLOR_NOTICE])
    assert '<br><br>'+SIZE_NOTICE in brief_description(data)

@pytest.mark.parametrize('material',['925실버','실버 925','silver925','925 Silver','sterling silver'])
def test_silver_notice_follows_color_notice_once(material):
    output=brief_description({'material':material,'size':'2cm','description':SILVER_NOTICE})
    assert output.endswith(COLOR_NOTICE+'<br>'+SILVER_NOTICE)
    assert output.count(SILVER_NOTICE)==1

@pytest.mark.parametrize('material',['신주, 무니켈도금','silver','실버도금','925 실버 도금','925실버 아님',''])
def test_colour_and_unconfirmed_or_plated_material_do_not_trigger_silver_notice(material):
    assert SILVER_NOTICE not in brief_description({'material':material,'description':'comment\n925실버 같은 빛\ndetail info\ncolor silver'})

def test_does_not_extract_facts_from_comment_or_invent_missing_values():
    result=brief_description({'material':'신주','size':'3cm','description':'comment\ncolor gold\nmaterial 925실버'})
    assert 'material 신주<br>color<br>size 3cm' in result
    assert SILVER_NOTICE not in result

def test_entered_values_are_escaped():
    assert 'material &lt;script&gt;' in brief_description({'material':'<script>'})
