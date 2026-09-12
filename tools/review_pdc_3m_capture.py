"""Review BB51 labelled capture evidence; produces a proposal, never applies it."""
from __future__ import annotations
import argparse,json
from pathlib import Path


def proposal(document):
    if document.get('pid')!='BB51' or not document.get('complete'):
        raise ValueError('A complete BB51 capture is required.')
    from capture_pdc_3m import capture_steps
    expected={x['key']:x for x in capture_steps()}
    records=document.get('records',[])
    keys=[(r.get('step') or {}).get('key') for r in records]
    if len(keys)!=len(set(keys)) or set(keys)!=set(expected):
        raise ValueError('Capture steps are missing or duplicated.')
    result={'pid':'BB51','serial':document.get('serial'),'momentary':{},'selectors':{},'detent_knobs':{},'issues':[],'absent':[]}
    poses={};used={};detents={}
    def assign(bit,name):
        if bit in used and used[bit]!=name:result['issues'].append(f'Contact {bit} identifies both {used[bit]} and {name}.')
        used[bit]=name
    for record in records:
        step=record['step'];key=step['key']
        if record.get('absent'):
            result['absent'].append(key);continue
        samples=record.get('samples') or []
        if not samples or not record.get('valid'):
            result['issues'].append(key+': no accepted recording');continue
        if any(s.get('serial')!=document.get('serial') for s in samples):
            result['issues'].append(key+': physical serial changed');continue
        bits=[set(s['buttons']) for s in samples]
        baseline=bits[0];rising=set.union(*bits)-baseline;falling=baseline-set.intersection(*bits)
        if step['kind']=='selector':
            group,index=key.split(':');poses.setdefault(group,{})[int(index)]=bits[-1];continue
        if step['kind'] in {'detent','fast'}:
            group,direction,*fast=key.split('_')
            detents.setdefault(group,{})[direction+('_fast' if fast else '')]={'rising':sorted(rising),'falling':sorted(falling),'states':[sorted(b) for b in bits]}
            continue
        if len(rising)!=1:
            result['issues'].append(f'{key}: expected one independent press contact, observed {sorted(rising)}');continue
        bit=next(iter(rising));result['momentary'][str(bit)]=key;assign(bit,key)
    for group,values in poses.items():
        wanted={int(k.split(':')[1]) for k in expected if k.startswith(group+':')}
        if set(values)!=wanted:
            result['issues'].append(group+': incomplete selector positions');continue
        shared=set.intersection(*values.values());table={}
        for value,bits in values.items():
            unique=bits-shared
            other=set.union(*(b for i,b in values.items() if i!=value))
            unique-=other
            if len(unique)!=1:
                result['issues'].append(f'{group}:{value}: no unique settled contact ({sorted(unique)})');continue
            bit=next(iter(unique));table[str(bit)]=value;assign(bit,group+':'+str(value))
        result['selectors'][group]=table
    for group,phases in detents.items():
        required={'dec','inc','dec_fast','inc_fast'}
        if set(phases)!=required:
            result['issues'].append(group+': missing slow or fast direction');continue
        # Slow captures identify one detent each. A fast movement may traverse
        # the slow contact, which is excluded from its independent fast phase.
        table={}
        for name in ('dec','inc'):
            rising=set(phases[name]['rising'])
            if len(rising)!=1:result['issues'].append(group+' '+name+': ambiguous detent');continue
            table[name]=next(iter(rising))
        for name in ('dec_fast','inc_fast'):
            rising=set(phases[name]['rising'])-set(table.values())
            if len(rising)!=1:result['issues'].append(group+' '+name+': ambiguous fast phase');continue
            table[name]=next(iter(rising))
        rest=set.intersection(*(set(p['falling']) for p in phases.values()))
        if len(rest)!=1:result['issues'].append(group+': ambiguous rest contact')
        else:table['rest']=next(iter(rest))
        result['detent_knobs'][group]=table
        for name,bit in table.items():assign(bit,group+':'+name)
    result['ready_for_review']=not result['issues']
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('capture',type=Path);args=parser.parse_args()
    print(json.dumps(proposal(json.loads(args.capture.read_text(encoding='utf-8'))),indent=2))
