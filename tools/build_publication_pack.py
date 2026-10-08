"""Build an explicit, gate-bound VE 0.2.2 localization release. Never publish.

All locations are CLI inputs. --preflight does not write a pack. The existing
runtime, source projection, media, complete localization report and independent
review must all be pinned before --build. No engine or launcher action exists.
"""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,re,zipfile
SLUG='vassalization_extended';VERSION='0.2.2';TARGET='1.20.0.4';STEAM='3813943691'
CANDIDATE='d7ae796a87981e4f9fc28e72eb90caf8978c4c2ba361705bb73af25048cb7bc5'
def require(ok,why):
 if not ok:raise ValueError(why)
def sha(data):return hashlib.sha256(data).hexdigest()
def record(data):return dict(bytes=len(data),sha256=sha(data))
def pin(p):return dict(path=p.as_posix(),**record(p.read_bytes()))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def data(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def inventory(files):return {k:record(v) for k,v in sorted(files.items())}
def tree(root):
 require(root.is_dir(),'Missing directory '+str(root));files={}
 for p in sorted(root.rglob('*')):
  require(not p.is_symlink() and not(getattr(p.lstat(),'st_file_attributes',0)&0x400),'Nested reparse point '+str(p))
  if p.is_file():files[p.relative_to(root).as_posix()]=p.read_bytes()
 require(len(files)==len({k.casefold() for k in files}),'Case collision');return files
def cp(row):
 p=Path(row['path']);require(record(p.read_bytes())=={k:row[k] for k in ['bytes','sha256']},'Stale pinned file '+str(p));return p
def put(root,files):
 for k,v in files.items():
  require(not PurePosixPath(k).is_absolute() and '..' not in PurePosixPath(k).parts and ':' not in k and '\\' not in k,'Unsafe output member')
  p=root/k;require(not p.exists(),'Refusing overwrite '+str(p));p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
def zipwrite(p,files):
 require(not p.exists(),'Refusing archive overwrite');p.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for k,v in sorted(files.items()):
   i=zipfile.ZipInfo(k,(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,v,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
def zipcheck(p,expected):
 with zipfile.ZipFile(p) as z:
  require(z.testzip() is None,'Archive CRC failed');require(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(expected),'Archive member inventory mismatch')
  require({k:record(z.read(k)) for k in z.namelist()}==expected,'Archive member hashes mismatch')
def localization_gate(p,mp):
 g=read(p);require(g['status']=='PASS_COMPLETE_LOCALIZATION' and g['mod']==SLUG and g['version']==VERSION and g['game_target']==TARGET,'Wrong complete gate')
 require(g['runtime_manifest']['sha256']==CANDIDATE and cp(g['runtime_manifest']).resolve()==mp.resolve(),'Gate candidate mismatch')
 r=read(cp(g['complete_localization_report']));scope=read(cp(g['scope_inventory']));approval=read(cp(g['independent_scope_review']))
 require(r['status']=='PASS_COMPLETE_LOCALIZATION' and r['remaining_required_gaps']==[] and r['runtime_manifest']['sha256']==CANDIDATE,'Incomplete localization report')
 require(approval['accepted'] is True and approval['status']=='PASS_COMPLETE_LOCALIZATION','Independent acceptance absent')
 require(approval['accepted_report_sha256']==g['complete_localization_report']['sha256'] and approval['accepted_scope_inventory_sha256']==g['scope_inventory']['sha256'],'Independent review does not bind exact report/scope')
 require(approval['mod']==SLUG and approval['version']==VERSION and approval['game_target']==TARGET and approval['remaining_required_gaps']==[],'Independent review scope differs')
 languages=read(cp(r['language_inventory']))['languages'];require(len(languages)==9 and set(r['languages'])==set(languages),'Required languages mismatch')
 require(scope['runtime_manifest']['sha256']==CANDIDATE and scope['remaining_required_gaps']==[],'Scope incomplete')
 for l in languages:
  x=r['languages'][l];require(x['status']=='PASS' and x['reviewed_keys']==44 and x['native_verified_keys']==44 and x['semantic_value_count']==48 and not x['missing_keys'] and not x['unresolved_variants'],'Incomplete language '+l)
  require(all(v=='PASS' for v in x['categories'].values()),'Incomplete category '+l)
  for ref in x['evidence']:cp(ref)
 require(r['counts']['internal_alias_cells_source_reviewed']==36 and r['counts']['authored_values_semantically_reviewed']==432,'Internal alias/semantic scope incomplete')
 return g
def verify(bundle):
 m=read(bundle/'07-VERIFICATION/manifest.json');require(m['version']==VERSION and m['mod']==SLUG,'Wrong pack')
 for name,rec in m['kit_files'].items():require(record((bundle/name).read_bytes())==rec,'Pack file changed '+name)
 require(set(tree(bundle))==set(m['kit_files'])|{'07-VERIFICATION/manifest.json','07-VERIFICATION/build-result.json'},'Pack inventory changed')
 for z in m['archives']:
  p=bundle/z['path'];require(record(p.read_bytes())==z['file'],'Archive container changed');zipcheck(p,z['members'])
 require(len(m['runtime'])==27,'Runtime count changed');return dict(status='BUILT_AND_VERIFIED',mod=SLUG,version=VERSION,runtime_files=27,archives=2,engine_launched=False,external_publication=False)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path);ap.add_argument('--runtime-manifest',type=Path);ap.add_argument('--text-root',type=Path);ap.add_argument('--images-root',type=Path);ap.add_argument('--projection-lock',type=Path);ap.add_argument('--complete-gate',type=Path);ap.add_argument('--output-dir',type=Path);ap.add_argument('--preflight',action='store_true');ap.add_argument('--build',action='store_true');ap.add_argument('--verify',type=Path);a=ap.parse_args()
 if a.verify:print(json.dumps(verify(a.verify)));return
 require(a.preflight!=a.build,'Choose preflight or build');require(all([a.source_root,a.runtime_manifest,a.text_root,a.images_root,a.projection_lock]),'Explicit input paths required')
 lock=read(a.projection_lock);mp=a.runtime_manifest;require(sha(mp.read_bytes())==CANDIDATE,'Wrong frozen candidate');m=read(mp);payload=tree(Path(m['runtime']));require(inventory(payload)=={x['path']:{k:x[k] for k in ['bytes','sha256']} for x in m['files']} and len(payload)==27,'Candidate runtime changed')
 source=tree(a.source_root);texts=tree(a.text_root);images=tree(a.images_root)
 require(inventory(source)==lock['source_files'] and inventory(texts)==lock['text_files'] and inventory(images)==lock['image_files'],'Projection inputs changed')
 require(source['tools/build_publication_pack.py']==Path(__file__).read_bytes(),'Public builder copy differs')
 require(all(source[k]==v for k,v in payload.items()),'Source/runtime bytes differ')
 require(all(not re.search(rb'(?<![A-Za-z0-9])[A-Za-z]:[/\\]|(?i:Users[/\\]Pavel)|OPENAI_API_KEY\s*=',v) for k,v in source.items() if Path(k).suffix in {'.py','.ps1','.md','.json','.txt','.mod','.yml','.gui'}),'Machine path or credential in portable source')
 meta=json.loads(texts['metadata.json']);require(meta['version']==VERSION and meta['candidate']=='RELEASE' and meta['compatibility_target']==TARGET and meta['nexus_file_description']=='For CK3 '+TARGET,'Wrong metadata fields')
 require(texts['description.en.md']==source['publishing/description.en.md'] and texts['README.md']==source['README.md'],'Public source/rendered copy differs')
 require(len(texts['description-steam.bbcode.txt'].decode().replace('\r\n','\n').replace('\n','\r\n').encode())<=8000,'Steam byte budget exceeded')
 require(images['thumbnail.png']==payload['thumbnail.png'] and images['cover-paradox-1920x1080.png']==source['publishing/media/cover-paradox-1920x1080.png'],'Published media changed')
 require(record(images['cover-paradox-1920x1080.jpg'])==lock['published_paradox_jpeg'],'Paradox16:9cover changed')
 public=payload['descriptor.mod'];require(b'version="0.2.2"' in public and b'name="Vassalization Extended"' in public and not re.search(rb'(?m)^\s*(remote_file_id|path|replace_path)\s*=',public),'Nonportable/wrong descriptor')
 if not a.complete_gate:
  require(a.preflight,'Complete localization gate required for build');print(json.dumps(dict(status='INPUTS_PREFLIGHT_PASS_GATE_PENDING',runtime_files=27,root_acceptance=False)));return
 gate=localization_gate(a.complete_gate,mp)
 if a.preflight:print(json.dumps(dict(status='INPUTS_AND_GATE_PREFLIGHT_PASS',runtime_files=27,external_publication=False)));return
 require(a.output_dir and not a.output_dir.exists(),'Fresh output folder required');out=a.output_dir.resolve()
 for p in [a.source_root,a.text_root,a.images_root,Path(m['runtime'])]:require(not out.is_relative_to(p.resolve()) and not p.resolve().is_relative_to(out),'Output overlaps source')
 out.mkdir(parents=True);steam={**payload,'descriptor.mod':public+f'remote_file_id="{STEAM}"\n'.encode()};wrapper=public+f'path="mod/{SLUG}"\n'.encode()
 put(out/'01-STEAM/runtime'/SLUG,steam);put(out/'01-STEAM/runtime',{SLUG+'.mod':wrapper});put(out/'02-TEXT',texts);put(out/'05-IMAGES',images);put(out/'06-GITHUB/source',source)
 paradox=f'03-PARADOX/vassalization-extended-{VERSION}-PARADOX.zip';nexus=f'04-NEXUS/vassalization-extended-{VERSION}-NEXUS-MANUAL.zip'
 manual={**{SLUG+'/'+k:v for k,v in payload.items()},SLUG+'.mod':wrapper,'INSTALL.txt':texts['INSTALL.txt']}
 archives=[]
 for path,files in [(paradox,payload),(nexus,manual)]:zipwrite(out/path,files);zipcheck(out/path,inventory(files));archives.append(dict(path=path,file=record((out/path).read_bytes()),members=inventory(files)))
 guide=f'''Vassalization Extended {VERSION} — publication pack
Prepared and localization-gated; external upload/public page/delivered bytes remain separate.
Target CK3 {TARGET}; portable runtime27files; gameplay/GUI/media unchanged from0.2.1.
Steam existing3813943691: 01-STEAM/runtime/{SLUG}; 02-TEXT/description-steam.bbcode.txt.
Paradox existing162059: {paradox}; 02-TEXT/description-paradox.html.
Nexus existing407: {nexus}; file version0.2.2; File Description: For CK3 {TARGET}.
GitHub existingG4VV4KH/-CK3-Vassalization-Extended: 06-GITHUB/source.
Keep current previews/gallery. 05-IMAGES includes full16:9Paradox cover and four screenshots.
Localization: all9languages;432authoredvalues;396visible nativecells;36internalaliases.
Complete report SHA256: {gate['complete_localization_report']['sha256']}
Independent acceptance SHA256: {gate['independent_scope_review']['sha256']}
No blanket gameplay/visual certification; source-bound native limits remain in report.
Do not enable duplicate versions or remove the mod from campaigns with its wars/contracts.
This snapshot does not update the mutable release registry or journal.
'''
 put(out,{'00-START-HERE.txt':guide.encode(),'PUBLICATION-STATUS.json':data(dict(status='PREPARED_NOT_PUBLISHED',version=VERSION,localization='COMPLETE_ACCEPTED',platform_ids=dict(steam=STEAM,paradox='162059',nexus='407'))),'07-VERIFICATION/localization-gate.json':a.complete_gate.read_bytes(),'07-VERIFICATION/projection-lock.json':a.projection_lock.read_bytes(),'07-VERIFICATION/runtime-manifest.json':mp.read_bytes(),'07-VERIFICATION/build_publication_pack.py':Path(__file__).read_bytes()})
 result=dict(status='BUILT_AND_VERIFIED',mod=SLUG,version=VERSION,runtime_files=27,archives=2,engine_launched=False,external_publication=False)
 put(out,{'07-VERIFICATION/build-result.json':data(result)})
 manifest=dict(mod=SLUG,version=VERSION,game_target=TARGET,runtime=inventory(payload),archives=archives,localization_gate=pin(a.complete_gate),source_projection=inventory(source),kit_files={k:v for k,v in inventory(tree(out)).items() if k!='07-VERIFICATION/build-result.json'})
 put(out,{'07-VERIFICATION/manifest.json':data(manifest)});print(json.dumps(verify(out)))
if __name__=='__main__':main()
