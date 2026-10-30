"""Проверить, упаковать и установить общие скиллы Codex/Claude Code (текстурирование — два этапа: заводская отделка и износ)."""
import argparse,ast,hashlib,importlib.util,json,os,re,shutil,sys,zipfile
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/'tools/asset_skills'
WORK=ROOT/'_asset_src/asset_skill_build'
NAMES=('blender-asset-workflow','weapon-asset-texturing','weapon-asset-wear','blender-vegetation-workflow','godot-asset-preparation')
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def managed_files(folder,provider):
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        rel=path.relative_to(folder)
        if provider=='claude' and rel.parts[0]=='agents':continue
        yield path,rel

def check_source(official=None):
    deps=WORK/'validation_deps'
    if deps.is_dir():sys.path.insert(0,str(deps))
    validator=None
    if official:
        spec=importlib.util.spec_from_file_location('skill_quick_validator',official);validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    report=[];common=(SOURCE/'_shared/working-rules.md').read_bytes()
    for name in NAMES:
        folder=SOURCE/name;content=(folder/'SKILL.md').read_text(encoding='utf8')
        match=re.match(r'^---\n(.*?)\n---\n',content,re.S);assert match,name
        front=match.group(1);assert re.search(r'^name: '+re.escape(name)+r'$',front,re.M)
        desc=re.search(r'^description: (.+)$',front,re.M);assert desc,name
        description=json.loads(desc.group(1));assert 0<len(description)<=1024
        assert '[TODO:' not in content,name
        if validator:
            passed,message=validator.validate_skill(folder);assert passed,(name,message)
        assert (folder/'references/working-rules.md').read_bytes()==common,name
        links=[]
        for file in folder.rglob('*.md'):
            text=file.read_text(encoding='utf-8-sig')
            for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',text):
                target=target.strip().strip('<>')
                if re.match(r'^[a-z]+:',target,re.I) or target.startswith('#'):continue
                target=target.split('#')[0]
                assert (file.parent/target).is_file(),(file,target)
                links.append({'file':str(file.relative_to(folder)),'target':target})
        scripts=list(folder.rglob('*.py'))
        for file in scripts:ast.parse(file.read_text(encoding='utf-8-sig'))
        # Читаем реальную YAML-метадату, когда официальный валидатор доступен.
        if validator:
            import yaml
            interface=yaml.safe_load((folder/'agents/openai.yaml').read_text(encoding='utf8'))
            assert '$'+name in interface['interface']['default_prompt']
            assert 25<=len(interface['interface']['short_description'])<=64
        report.append({'skill':name,'entry_lines':len(content.splitlines()),'reference_links':len(links),'scripts_parsed':len(scripts),'official_validator':bool(validator)})
    WORK.mkdir(parents=True,exist_ok=True)
    (WORK/'source_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('SOURCE_VALIDATED',len(report),'skills',sum(x['reference_links'] for x in report),'local reference links',flush=True)
    return report

def package():
    archive=WORK/'RING_Asset_Skills_Codex_Claude_Code.zip';rows=[]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for provider,label in [('codex','Codex'),('claude','Claude_Code')]:
            for name in NAMES:
                for path,rel in managed_files(SOURCE/name,provider):
                    target=label+'/'+name+'/'+rel.as_posix();z.write(path,target);rows.append({'path':target,'sha256':sha(path)})
        z.write(ROOT/'docs/asset_skills.md','INSTALL_AND_USAGE.md')
        z.writestr('manifest.json',json.dumps(rows,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
    (WORK/'package_validation.json').write_text(json.dumps({'archive':str(archive),'sha256':sha(archive),'managed_files':len(rows),'providers':['Codex','Claude Code']},indent=2),encoding='utf8')
    print('PACKAGE_VERIFIED',len(rows),'files',archive,flush=True)
    return archive

def install(codex_root,claude_root):
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S');backup=ROOT/'_asset_src/asset_skill_backups'/stamp
    records=[]
    for provider,destination in [('codex',codex_root),('claude',claude_root)]:
        destination=destination.resolve();destination.mkdir(parents=True,exist_ok=True)
        for name in NAMES:
            target=destination/name
            assert target.resolve().parent==destination,'Target escaped intended skill root'
            # Существующие версии копируются целиком до замены известных файлов.
            if target.exists():
                assert not target.is_symlink(),'Linked existing skill requires a deliberate destination'
                shutil.copytree(target,backup/provider/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            target.mkdir(exist_ok=True)
            hashes=[]
            for src,rel in managed_files(SOURCE/name,provider):
                dst=target/rel
                assert dst.resolve().is_relative_to(target.resolve()),dst
                dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert sha(src)==sha(dst),dst
                hashes.append({'path':rel.as_posix(),'sha256':sha(dst)})
            # Файлы, которых больше нет в исходнике (переехавшие справки), убираются: прежняя версия уже в резервной копии.
            keep={h['path'] for h in hashes}
            for old in sorted(target.rglob('*'),reverse=True):
                rel=old.relative_to(target).as_posix()
                if old.is_file() and rel not in keep and '__pycache__' not in old.parts and not (provider=='claude' and rel.startswith('agents/')):
                    old.unlink()
                elif old.is_dir() and not any(old.iterdir()):
                    old.rmdir()
            records.append({'provider':provider,'skill':name,'root':str(target),'files':hashes})
    report={'installed':records,'backup_root':str(backup),'package_source':str(SOURCE)}
    (WORK/'installation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('INSTALLED_AND_HASH_VERIFIED',len(records),'skill copies; backups:',backup,flush=True)
    return report

def verify_installed():
    report=json.loads((WORK/'installation.json').read_text(encoding='utf8'))
    for row in report['installed']:
        root=Path(row['root'])
        for file in row['files']:assert sha(root/file['path'])==file['sha256'],root/file['path']
    for name in NAMES:
        codex=next(Path(r['root']) for r in report['installed'] if r['provider']=='codex' and r['skill']==name)
        claude=next(Path(r['root']) for r in report['installed'] if r['provider']=='claude' and r['skill']==name)
        for src,rel in managed_files(SOURCE/name,'claude'):assert sha(codex/rel)==sha(claude/rel)==sha(src),(name,rel)
        # Набор файлов копии Codex совпадает с исходником: лишних (переехавших) нет.
        want={rel.as_posix() for _,rel in managed_files(SOURCE/name,'codex')}
        got={f.relative_to(codex).as_posix() for f,_ in ((f,0) for f in codex.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
        assert got==want,(name,sorted(got^want))
    print('INSTALLED_PARITY_PASS',len(report['installed']),'copies',flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true');parser.add_argument('--package',action='store_true');parser.add_argument('--install',action='store_true');parser.add_argument('--verify-installed',action='store_true')
    current=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'
    # На текущем компьютере ~/.codex/skills уже зарегистрирован и содержит исходные навыки.
    default_codex=current if (current/'blender-asset-workflow/SKILL.md').is_file() else Path.home()/'.agents/skills'
    parser.add_argument('--codex-root',type=Path,default=default_codex);parser.add_argument('--claude-root',type=Path,default=Path.home()/'.claude/skills')
    parser.add_argument('--official-validator',type=Path,default=Path.home()/'.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    args=parser.parse_args()
    if args.check or args.package or args.install or not args.verify_installed:check_source(args.official_validator if args.official_validator.is_file() else None)
    if args.package:package()
    if args.install:install(args.codex_root,args.claude_root)
    if args.verify_installed:verify_installed()
if __name__=='__main__':main()
