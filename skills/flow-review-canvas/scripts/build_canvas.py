#!/usr/bin/env python3
"""Build a portable wired flow review board using only the Python standard library."""
import argparse, base64, hashlib, html, json, math, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def embedded(source, name):
    match=re.search(r'<script type="application/json" id="'+name+r'">(.*?)</script>',source,re.S)
    if not match: raise ValueError(f'Missing embedded {name} JSON')
    return json.loads(match[1])

def validate(model):
    if not isinstance(model,dict) or model.get('version')!=2: raise ValueError('Expected canvas model version 2')
    flows=model.get('flows')
    if not isinstance(flows,list) or not flows: raise ValueError('At least one flow is required')
    ids=set(); flow_ids=set()
    for flow in flows:
        if not isinstance(flow,dict):raise ValueError('Each flow must be an object')
        for key in ('title','desc','foot'):
            if not isinstance(flow.get(key),str):raise ValueError(f'Flow {key} must be text')
        if not isinstance(flow.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]+',flow['id']) or flow['id'] in flow_ids: raise ValueError('Flow IDs must be unique strings')
        flow_ids.add(flow['id'])
        if not isinstance(flow.get('steps'),list) or not flow['steps']: raise ValueError('Each flow needs at least one screen')
        for step in flow['steps']:
            if not isinstance(step,dict):raise ValueError('Each screen must be an object')
            sid=step.get('id')
            if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',sid) or sid in ids: raise ValueError('Screen IDs must be unique CSS-safe strings')
            ids.add(sid)
            for key in ('title','copy','body','caption'):
                if not isinstance(step.get(key),str): raise ValueError(f'{sid}: {key} must be text')
            step.setdefault('tag',model.get('brand','Product'))
    positions=model.setdefault('positions',{})
    for fi,flow in enumerate(flows):
        for si,step in enumerate(flow['steps']):
            pos=positions.setdefault(step['id'],{'x':230+620*si,'y':150+690*fi,'w':504})
            for key in ('x','y'):
                if type(pos.get(key)) not in (int,float) or not math.isfinite(pos[key]) or pos[key]<0: raise ValueError(f'{step["id"]}: invalid {key}')
            if 'w' in pos and (not isinstance(pos['w'],(int,float)) or not 180<=pos['w']<=1100):raise ValueError('Screen width must be 180–1100 canvas pixels')
    if 'edges' not in model:
        model['edges']=[{'from':a['id'],'to':b['id'],'type':'sequence','label':''} for f in flows for a,b in zip(f['steps'],f['steps'][1:])]
    for edge in model['edges']:
        if edge.get('from') not in ids or edge.get('to') not in ids: raise ValueError('Wire references an unknown screen')
        if edge.get('type') not in ('sequence','branch','return'):raise ValueError('Wire type must be sequence, branch, or return')
        edge.setdefault('label','')
    model.setdefault('annotations',[])
    aids=set()
    for a in model['annotations']:
        aid=a.get('id')
        if not isinstance(aid,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',aid) or aid in aids:raise ValueError('Feedback IDs must be unique CSS-safe strings')
        aids.add(aid)
        if a.get('type') not in ('note','comment') or not isinstance(a.get('text',''),str): raise ValueError('Invalid feedback item')
        if a['type']=='comment' and a.get('screenId') not in ids: raise ValueError('A comment references a missing screen; migrate it before building')
    model.setdefault('brand','Product')
    model.setdefault('title',model['brand']+' flow review')
    model.setdefault('boardId','board-'+hashlib.sha256('|'.join(sorted(ids)).encode()).hexdigest()[:12])
    if not re.fullmatch(r'[A-Za-z0-9_-]+',model['boardId']):raise ValueError('boardId must contain only letters, numbers, hyphens or underscores')
    width=max(3200,math.ceil(max(p['x']+p.get('w',504)+500 for p in positions.values())))
    height=max(1500,math.ceil(max(p['y']+p.get('w',504)*760/840+450 for p in positions.values())))
    model['canvas']={'width':width,'height':height}
    return model

def icon_data(values, directory):
    result={}
    for name,value in values.items():
        if not isinstance(value,str):raise ValueError('Icon values must be paths or data URLs')
        if value.startswith('data:image/'):
            if not re.match(r'^data:image/(png|jpeg|webp|gif);base64,',value):raise ValueError('Use raster PNG/JPEG/WebP/GIF icon data URLs')
            result[name]=value;continue
        f=(directory/value).resolve()
        mime={'.png':'png','.jpg':'jpeg','.jpeg':'jpeg','.webp':'webp','.gif':'gif'}.get(f.suffix.lower())
        if not mime:raise ValueError('Icons must be PNG/JPEG/WebP/GIF; export ICNS/SVG separately first')
        result[name]='data:image/'+mime+';base64,'+base64.b64encode(f.read_bytes()).decode()
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model',type=Path,help='Board JSON or returned feedback JSON')
    ap.add_argument('--from-html',type=Path,help='Existing board: inherit embedded model and icons')
    ap.add_argument('--icons',type=Path,help='JSON map of display names/keys to image paths or data URLs')
    ap.add_argument('--css',type=Path,help='Reviewed product-specific CSS overrides')
    ap.add_argument('--brand',help='Product name override')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--force',action='store_true',help='Explicitly replace an existing output; exports remain separate')
    args=ap.parse_args()
    if args.out.exists() and not args.force:ap.error('Output exists; use a new filename or explicitly pass --force')
    model=None;icons={}
    if args.from_html:
        source=args.from_html.read_text();model=embedded(source,'data');icons=embedded(source,'icons')
    if args.model:model=json.loads(args.model.read_text())
    if model is None:model=json.loads((ROOT/'assets/example.json').read_text())
    if args.brand:model['brand']=args.brand
    model=validate(model)
    if args.icons:icons.update(icon_data(json.loads(args.icons.read_text()),args.icons.parent))
    icons=icon_data(icons,Path('.'))
    out=(ROOT/'assets/canvas.html').read_text()
    values={'MODEL':json.dumps(model,ensure_ascii=False).replace('<','\\u003c'),'ICONS':json.dumps(icons).replace('<','\\u003c'),'TITLE':html.escape(model['title']),'WIDTH':str(model['canvas']['width']),'HEIGHT':str(model['canvas']['height']),'CSS':args.css.read_text() if args.css else ''}
    # One substitution pass prevents user-authored text from becoming a second template instruction.
    out=re.sub(r'@@(MODEL|ICONS|TITLE|WIDTH|HEIGHT|CSS)@@',lambda m:values[m[1]],out)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(out)
    print(json.dumps({'path':str(args.out.resolve()),'flows':len(model['flows']),'screens':sum(len(f['steps']) for f in model['flows']),'feedback_items':len(model['annotations']),'board_id':model['boardId']}))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:raise SystemExit(str(exc))
