import pytest
from app.services.brief_description_service import brief_description,SIZE_NOTICE,COLOR_NOTICE,SILVER_NOTICE

@pytest.mark.parametrize('newline',['\n','\r\n'])
def test_copies_entered_detail_block_exactly_without_rewriting_or_html(newline):
    block=newline.join(['detail info','material 신주, 무니켈도금','color silver & gold',
        'size 총 체인 길이 약 60cm  ','',SIZE_NOTICE,COLOR_NOTICE,'','직접 입력한 추가 안내',''])
    data={'description':'comment'+newline+'멋진 목걸이'+newline+block,'material':'다른 소재','size':'free'}
    assert brief_description(data)==block
    assert '<br' not in brief_description(data) and '<div' not in brief_description(data)


def test_manual_block_does_not_invent_notices_or_override_operator_text():
    block='  Detail Info :\nmaterial 925실버\nsize: 직접 입력한 치수\n'
    assert brief_description({'description':'comment\n설명\n'+block,'material':'신주'})==block

@pytest.mark.parametrize('material',['925실버','실버 925','silver925','925 Silver','sterling silver'])
def test_silver_notice_follows_color_notice_once(material):
    output=brief_description({'material':material,'size':'2cm','description':SILVER_NOTICE})
    assert output.endswith(COLOR_NOTICE+'\n'+SILVER_NOTICE)
    assert output.count(SILVER_NOTICE)==1

@pytest.mark.parametrize('material',['신주, 무니켈도금','silver','실버도금','925 실버 도금','925실버 아님',''])
def test_colour_and_unconfirmed_or_plated_material_do_not_trigger_silver_notice(material):
    assert SILVER_NOTICE not in brief_description({'material':material,'description':'comment\n925실버 같은 빛\ndetail info\ncolor silver'})

def test_does_not_extract_facts_from_comment_or_invent_missing_values():
    result=brief_description({'material':'신주','size':'3cm','description':'comment\ncolor gold\nmaterial 925실버'})
    assert 'material 신주\ncolor\nsize 3cm' in result
    assert SILVER_NOTICE not in result

def test_plain_text_fallback_does_not_encode_characters_as_html():
    assert 'material silver & gold' in brief_description({'material':'silver & gold'})
