from app.services.html_parser_service import parse_html, compile_template, sanitize
from app.services.style_clustering_service import cluster,select_stable,similarity

def sample(i,style='p'):
    return {'product_no':i,'parsed':parse_html(f'<div class="brand"><{style}>제품 설명 {i}</{style}><img src="https://shop.com/{i}.jpg"/><h3>SIZE</h3><p>{i}cm</p><h3>NOTICE</h3><p>교환은 구매 안내를 확인해주세요.</p></div>')}
def test_sanitization():
    value=sanitize('<script>alert(1)</script><iframe src="x"></iframe><p onClick="bad()" style="background:url(x);position:fixed;color:red">안내</p><img src="javascript:alert(1)" onerror="bad()">')
    assert 'script' not in value and 'iframe' not in value and 'onclick' not in value.lower() and 'onerror' not in value and 'url(' not in value and 'position' not in value
    assert 'color:red' in value

def test_structure_ignores_unique_values():
    assert similarity(sample(1)['parsed'],sample(999)['parsed'])==1
    template=compile_template([sample(901),sample(902),sample(903)])
    value=str(template)
    assert '901cm' not in value and '제품 설명 901' not in value and 'shop.com' not in value
    assert '교환은 구매 안내' in value

def test_new_singleton_not_selected():
    odd={'product_no':0,'parsed':parse_html('<table><tr><td>새로운 형식</td></tr></table><section><div><p>안내 문구</p></div></section>')}
    samples=[odd]+[sample(i) for i in range(1,5)]
    chosen=select_stable(cluster(samples))
    assert chosen and chosen['count']==4 and chosen['latest_rank']==1

def test_recent_stable_beats_old_majority():
    samples=[sample(i,'section') for i in range(3)]+[sample(i) for i in range(3,30)]
    assert select_stable(cluster(samples))['latest_rank']==0

def test_insufficient_evidence_blocks():
    assert select_stable(cluster([sample(1),sample(2)])) is None
