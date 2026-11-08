"""Reproducible size/encoding derivatives; originals remain byte-identical archives.
Run with Pillow installed: python scripts/prepare_assets.py (from backend).
"""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'assets'
PUBLIC = ROOT / 'v1'
PETS = [('initial','初始.png'),('starting','启动（完成2个步骤） .png'),
        ('flow','渐入佳境（完成5个步骤）.png'),('reward','小闭环奖励（一个任务全部完成）.png'),
        ('distracted','走神.png'),('emergency_dark','紧急暗黑模式态.png')]


def save_image(im, folder, stem, size, fmt, **options):
    im = im.copy(); im.thumbnail(size, Image.Resampling.LANCZOS)
    buf = io.BytesIO(); im.save(buf, format=fmt, **options); data=buf.getvalue()
    sha=hashlib.sha256(data).hexdigest()
    suffix='png' if fmt=='PNG' else 'jpg'
    name=f'{stem}-{sha[:12]}.{suffix}'
    path=PUBLIC/folder/name; path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return {'url':f'/api/assets/v1/{folder}/{name}','width':im.width,'height':im.height,
            'bytes':len(data),'sha256':sha}


def build():
    manifest={'version':'2026-11-08-v1','pets':{},'receipts':{},
              'journal':{'available':False,'background':None,'reason':'awaiting_supplied_background'},
              'originals':{}}
    for archive in ('states.zip','receipts.zip'):
        data=(ROOT/'originals'/archive).read_bytes()
        manifest['originals'][archive]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    with zipfile.ZipFile(ROOT/'originals/states.zip') as z:
        for key,filename in PETS:
            raw=z.read('状态/'+filename);im=Image.open(io.BytesIO(raw))
            asset=save_image(im,'pets',key,(512,512),'PNG',optimize=True)
            asset.update(source='状态/'+filename,source_sha256=hashlib.sha256(raw).hexdigest(),
                         alpha=True,automatic_trigger=key!='emergency_dark')
            manifest['pets'][key]=asset
    with zipfile.ZipFile(ROOT/'originals/receipts.zip') as z:
        for filename in sorted(n for n in z.namelist() if n.lower().endswith('.jpg')):
            raw=z.read(filename); im=Image.open(io.BytesIO(raw));key=filename.split('/')[1][:3]
            asset=save_image(im,'receipts',key,(1280,1920),'JPEG',quality=90,optimize=True)
            asset['preview']=save_image(im,'receipts',key+'-preview',(384,576),'JPEG',quality=85,optimize=True)
            asset.update(source=filename,source_sha256=hashlib.sha256(raw).hexdigest())
            # Source coordinates, measured against all 12 original 1696x2528 designs.
            # No artwork is painted over here: client covers the baked date using a blank-paper patch.
            date_y={'1.1':2305,'1.2':2310,'1.3':2307,'2.1':2280,'2.2':2310,'2.3':2305,
                    '3.1':2270,'3.2':2310,'3.3':2270,'4.1':2270,'4.2':2245,'4.3':2308}[key]
            asset['composition']={'coordinate_space':[1696,2528],
                'text_box':{'x':280,'y':1940,'width':1120,'height':250},
                'date_cover':{'x':1040,'y':date_y,'width':470,'height':75},
                'date_patch_source':{'x':400,'y':date_y,'width':470,'height':75},
                'date_text_box':{'x':1040,'y':date_y,'width':470,'height':75},
                'baked_date':True,'date_source':'receipt_event.occurred_date',
                'overflow':'wrap_then_reduce_font_or_request_shorter_text_never_clip',
                'preview_and_export':'same_canvas_composition'}
            manifest['receipts'][key]=asset
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'pets':len(manifest['pets']),'receipts':len(manifest['receipts']),
                      'runtime_bytes':sum(p.stat().st_size for p in PUBLIC.rglob('*') if p.is_file())}))

if __name__=='__main__':build()
