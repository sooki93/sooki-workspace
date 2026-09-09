from difflib import SequenceMatcher
from app.services.html_parser_service import section_order

def similarity(a,b):
    structure=SequenceMatcher(None,a['tokens'],b['tokens'],autojunk=False).ratio()
    order=SequenceMatcher(None,section_order(a),section_order(b),autojunk=False).ratio()
    return .8*structure+.2*order

def cluster(samples,threshold=.88):
    groups=[]
    for index,sample in enumerate(samples):
        sample={**sample,'rank':index}
        match=next((g for g in groups if all(similarity(sample['parsed'],x['parsed'])>=threshold for x in g['samples'])),None)
        if match: match['samples'].append(sample)
        else: groups.append({'id':f'STYLE_{len(groups)+1}','samples':[sample]})
    for g in groups:
        ranks={s['rank'] for s in g['samples']}
        recent=min(ranks); streak=0
        while recent+streak in ranks: streak+=1
        g.update({'count':len(ranks),'latest_rank':recent,'recent10_count':sum(r<10 for r in ranks),'consecutive_count':streak,'stable':len(ranks)>=3 and recent<10})
    return groups

def select_stable(groups):
    stable=[g for g in groups if g['stable']]
    return min(stable,key=lambda g:(g['latest_rank'],-g['recent10_count'],-g['consecutive_count'],-g['count'])) if stable else None
