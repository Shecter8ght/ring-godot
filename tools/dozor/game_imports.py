"""Apply the project's explicit VRAM, mipmap and roughness-filter settings to DOZOR only."""
import pathlib,re,json
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=ROOT/'assets/models/attachments/dozor'
def setparam(text,key,value):
    pattern=r'^'+re.escape(key)+r'=.*$'
    if re.search(pattern,text,re.M):return re.sub(pattern,key+'='+value,text,flags=re.M)
    return text.rstrip()+'\n'+key+'='+value+'\n'
changed=[]
for p in OUT.glob('*.png.import'):
    text=p.read_text(encoding='utf-8');old=text
    for key,val in [('compress/mode','2'),('mipmaps/generate','true'),('detect_3d/compress_to','0')]:text=setparam(text,key,val)
    if '_normal.' in p.name:
        text=setparam(text,'compress/normal_map','1');text=setparam(text,'roughness/mode','1')
    elif '_orm.' in p.name:
        atlas='p' if 'dozor_p_' in p.name else 'f1'
        text=setparam(text,'roughness/mode','3')
        text=setparam(text,'roughness/src_normal','"res://assets/models/attachments/dozor/dozor_'+atlas+'_normal.png"')
    else:text=setparam(text,'roughness/mode','1')
    if text!=old:p.write_text(text,encoding='utf-8');changed.append(p.name)
for p in OUT.glob('*.gltf.import'):
    text=p.read_text(encoding='utf-8');old=text
    text=setparam(text,'meshes/generate_lods','true');text=setparam(text,'meshes/ensure_tangents','true')
    if text!=old:p.write_text(text,encoding='utf-8');changed.append(p.name)
print('DOZOR import settings updated',changed)
