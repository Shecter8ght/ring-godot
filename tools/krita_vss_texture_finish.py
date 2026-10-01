"""Встроенный Krita Runner: настоящие слоистые .kra, композит и карты PBR.

kritarunner --script krita_vss_texture_finish --function main DIR
"""
from pathlib import Path
import json, traceback
from krita import Krita, InfoObject
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtCore import QByteArray, QCoreApplication

def pixels(path):
    image=QImage(str(path)).convertToFormat(QImage.Format_ARGB32)
    if image.isNull():raise RuntimeError('Missing image: '+str(path))
    ptr=image.constBits();ptr.setsize(image.byteCount())
    return QByteArray(bytes(ptr))

def finish(folder,app):
    manifest=json.loads((folder/'layers.json').read_text(encoding='utf-8')); n=manifest['size']
    document=app.createDocument(n,n,manifest['name'],'RGBA','U8','sRGB-elle-V2-srgbtrc.icc',120.0)
    document.setBatchmode(True)
    for background in document.rootNode().childNodes():background.setVisible(False)
    groups={}
    for label in ('Base Color','ORM','Normal','Guides'):
        group=document.createNode(label,'grouplayer');document.rootNode().addChildNode(group,None);groups[label]=group
        group.setVisible(label=='Base Color')
        if label in ('Base Color','ORM','Normal'):
            bg=document.createNode('UV padding background','paintlayer');group.addChildNode(bg,None)
            fill=QImage(n,n,QImage.Format_ARGB32)
            fill.fill(QColor(*{'Base Color':(6,8,10),'ORM':(255,128,0),'Normal':(128,128,255)}[label]))
            ptr=fill.constBits();ptr.setsize(fill.byteCount());bg.setPixelData(QByteArray(bytes(ptr)),0,0,n,n)
            bg.setLocked(True)
    for layer in manifest['layers']:
        node=document.createNode(layer['name'],'paintlayer');groups[layer['group']].addChildNode(node,None)
        if not node.setPixelData(pixels(folder/layer['file']),0,0,n,n):raise RuntimeError('setPixelData failed')
        node.setVisible(True)
        if layer['group']=='Guides':node.setLocked(True)
    document.refreshProjection();document.waitForDone();QCoreApplication.processEvents()
    kra=folder/'Textures.kra'
    if not document.saveAs(str(kra)):raise RuntimeError('KRA save failed')
    cfg=InfoObject();cfg.setProperty('alpha',False);cfg.setProperty('compression',6)
    exports={}
    for name,group in [('basecolor','Base Color'),('orm','ORM'),('normal','Normal')]:
        for label,node in groups.items():node.setVisible(label==group)
        document.refreshProjection();document.waitForDone()
        path=folder/(name+'.png')
        if not document.exportImage(str(path),cfg):raise RuntimeError('PNG export failed: '+name)
        exports[name]=str(path)
    for label,node in groups.items():node.setVisible(label=='Base Color')
    document.refreshProjection();document.waitForDone();document.save();document.close()
    reopened=app.openDocument(str(kra));reopened.setBatchmode(True);reopened.waitForDone()
    tree=[{'name':g.name(),'visible':g.visible(),'layers':[c.name() for c in g.childNodes()]} for g in reopened.rootNode().childNodes()]
    reopened.close()
    result={'status':'PASS','Krita':app.version(),'file':str(kra),'size':n,'groups':tree,'exports':exports}
    (folder/'krita-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def main(args=None):
    root=Path(args[0]) if args else Path('E:/Games/RING-godot/_asset_src/vss_textured')
    identifier=args[1] if args and len(args)>1 else None
    marker=root/'krita-progress.json'
    marker.write_text(json.dumps({'phase':'started'}),encoding='utf-8')
    try:
        app=Krita.instance();reports=[];processed=0
        for manifest in sorted(root.glob('*/**/layers.json')):
            if identifier and manifest.relative_to(root).parts[0]!=identifier:
                cached=json.loads((manifest.parent/'krita-report.json').read_text(encoding='utf8'))
                if cached['status']!='PASS':raise RuntimeError('Other atlas not verified')
                reports.append(cached)
                continue
            marker.write_text(json.dumps({'phase':'processing','file':str(manifest)}),encoding='utf-8')
            reports.append(finish(manifest.parent,app))
            processed+=1
        if not processed:raise RuntimeError('No atlas matches requested asset')
        marker.write_text(json.dumps({'status':'PASS','reports':reports},ensure_ascii=False,indent=2),encoding='utf-8')
    except Exception:
        marker.write_text(json.dumps({'status':'FAIL','traceback':traceback.format_exc()},ensure_ascii=False,indent=2),encoding='utf-8')
        raise
