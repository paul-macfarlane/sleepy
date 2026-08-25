import json,subprocess,sys
# Usage: board.py DRAFT_ID [N] [SLOT]  — prints user's roster, position counts, last 5 picks,
# and the top-N available players by Sleeper search_rank with injury tags (🚑 Out/IR/PUP/Doubtful, ⚠️ Questionable).
did=sys.argv[1]; n=int(sys.argv[2]) if len(sys.argv)>2 else 40; slot=int(sys.argv[3]) if len(sys.argv)>3 else 6
import os
P=json.load(open(os.path.expanduser('~/sleepy/cache/players.json')))
picks=json.loads(subprocess.check_output(['curl','-s',f'https://api.sleeper.app/v1/draft/{did}/picks']))
gone={p['player_id'] for p in picks}
mine=[p for p in picks if p['draft_slot']==slot]
print('MY ROSTER:', ', '.join(f"{p['metadata']['position']} {p['metadata']['last_name']}" for p in mine))
from collections import Counter
print('POS COUNTS DRAFTED:', dict(Counter(p['metadata']['position'] for p in picks)))
print('LAST 5:', ', '.join(f"{p['metadata']['position']} {p['metadata']['last_name']}" for p in picks[-5:]))
act=[p for p in P.values() if p.get('active') and p.get('search_rank') and p['search_rank']<9999 and p.get('position') in ('QB','RB','WR','TE') and p.get('team') and p['player_id'] not in gone]
act.sort(key=lambda p:p['search_rank'])
print(f'TOP {n} AVAILABLE:')
def inj(p):
    st=p.get('injury_status')
    if not st: return ''
    tag='🚑' if st in ('Out','IR','PUP','Doubtful','NA','Sus') else '⚠️'
    return f"  {tag} {st}: {p.get('injury_body_part') or '?'} {p.get('injury_notes') or ''}".rstrip()
for p in act[:n]: print(f"{p['search_rank']:3d} {p['position']:2s} {p['first_name']} {p['last_name']} ({p['team']}, {p.get('age')}){inj(p)}")
