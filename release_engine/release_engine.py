from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from zipfile import ZipFile
import hashlib, json, re

class ReleaseEngine:
    def __init__(self, base_path: Path, approval_gate, update_manager, worker_manager, event_bus):
        self.base_path=base_path; self.approval_gate=approval_gate; self.update_manager=update_manager; self.worker_manager=worker_manager; self.event_bus=event_bus
        self.release_dir=base_path/'data'/'releases'; self.history_dir=base_path/'data'/'release_history'; self.package_dir=base_path/'release_packages'; self.docs_dir=base_path/'docs'/'releases'
        for d in [self.release_dir,self.history_dir,self.package_dir,self.docs_dir]: d.mkdir(parents=True,exist_ok=True)
    def create(self, approval_id: Optional[str]=None, release_type: str='patch') -> Dict[str, Any]:
        approval=self._load_approved_item(approval_id); now=datetime.now().astimezone(); release_id=f"REL-{now.strftime('%Y%m%d-%H%M%S')}"
        cur=self._get_current_version(); nxt=self._bump_version(cur, release_type); ws=self.release_dir/release_id; ws.mkdir(parents=True,exist_ok=True)
        manifest=self._build_manifest(release_id, approval, nxt, release_type); manifest_path=ws/'release_manifest.json'; manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        notes_path=self._write_release_notes(ws,release_id,approval,nxt); changelog_path=self._write_changelog(ws,release_id,approval,nxt); version_path=self._write_version(ws,nxt,release_id); report_path=self._write_report(ws,release_id,approval,nxt)
        package_path=self._make_package(release_id,[manifest_path,notes_path,changelog_path,version_path,report_path]); sha=self._sha256(package_path); sha_path=ws/'SHA256.txt'; sha_path.write_text(sha,encoding='utf-8')
        artifacts=[{'type':'manifest','path':str(manifest_path)},{'type':'release_notes','path':str(notes_path)},{'type':'changelog_draft','path':str(changelog_path)},{'type':'version_candidate','path':str(version_path)},{'type':'release_report','path':str(report_path)},{'type':'package','path':str(package_path)},{'type':'sha256','path':str(sha_path)}]
        release={'release_id':release_id,'created_at':now.isoformat(timespec='seconds'),'status':'completed','approval_id':approval.get('approval_id',''),'product_id':approval.get('product_id',''),'plan_id':approval.get('plan_id',''),'dev_run_id':approval.get('dev_run_id',''),'qa_id':approval.get('qa_id',''),'doc_id':approval.get('doc_id',''),'version':nxt,'previous_version':cur,'release_type':release_type,'package_path':str(package_path),'manifest_path':str(manifest_path),'release_notes_path':str(notes_path),'sha256':sha,'artifacts':artifacts,'next_stage':'deploy_ready'}
        rel_path=self.release_dir/f'{release_id}.json'; hist_path=self.history_dir/f'{release_id}.json'; release['release_path']=str(rel_path); release['history_path']=str(hist_path); rel_path.write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8'); hist_path.write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf-8')
        self.event_bus.publish('RELEASE_CREATED', {'release_id':release_id,'approval_id':release['approval_id'],'version':nxt,'package_path':str(package_path)})
        self.worker_manager.run('audit_log_worker', {'actor':'ReleaseEngine','action':'RELEASE_CREATED','target':release_id,'reason':'Approved item converted into release package','result':'success','metadata':{'approval_id':release['approval_id'],'version':nxt,'release_type':release_type,'package_path':str(package_path),'sha256':sha}})
        return release
    def latest(self):
        files=sorted(self.history_dir.glob('REL-*.json'), reverse=True)
        if not files: raise FileNotFoundError('No release found.')
        return json.loads(files[0].read_text(encoding='utf-8'))
    def list_releases(self, limit:int=10):
        out=[]
        for p in sorted(self.history_dir.glob('REL-*.json'), reverse=True):
            try:
                d=json.loads(p.read_text(encoding='utf-8')); out.append({'release_id':d.get('release_id',p.stem),'version':d.get('version',''),'status':d.get('status',''),'created_at':d.get('created_at','')})
            except Exception: continue
            if len(out)>=limit: break
        return out
    def _load_approved_item(self, approval_id):
        if approval_id:
            item=self.approval_gate.get(approval_id)
            if item.get('status')!='approved': raise PermissionError(f'Approval is not approved: {approval_id}')
            return item
        h=self.base_path/'data'/'approval_history'; approved=[]
        for p in sorted(h.glob('APP-*.json'), reverse=True):
            try:
                d=json.loads(p.read_text(encoding='utf-8'))
                if d.get('status')=='approved': approved.append(d)
            except Exception: continue
        if not approved: raise FileNotFoundError('No approved approval item found. Run approve approve first.')
        return approved[0]
    def _get_current_version(self):
        try:
            v=self.update_manager.get_version(); return str(v.get('version') or v.get('current_version') or '1.6.0')
        except Exception: return '1.6.0'
    def _bump_version(self, version, release_type):
        m=re.search(r'(\d+)\.(\d+)\.(\d+)', str(version))
        if not m: return '1.7.0'
        major,minor,patch=map(int,m.groups())
        if release_type=='major': return f'{major+1}.0.0'
        if release_type=='minor': return f'{major}.{minor+1}.0'
        return f'{major}.{minor}.{patch+1}'
    def _build_manifest(self, release_id, approval, version, release_type):
        return {'release_id':release_id,'version':version,'release_type':release_type,'approval_id':approval.get('approval_id'),'product_id':approval.get('product_id'),'plan_id':approval.get('plan_id'),'dev_run_id':approval.get('dev_run_id'),'qa_id':approval.get('qa_id'),'doc_id':approval.get('doc_id'),'qa_decision':approval.get('qa_decision'),'qa_score':approval.get('qa_score'),'documents':approval.get('documents',[]),'release_allowed':approval.get('release_allowed',False)}
    def _write_release_notes(self, ws, rid, app, ver):
        p=ws/'RELEASE_NOTES.md'; p.write_text(f"# Release Notes - {ver}\n\nRelease ID: `{rid}`\n\nApproval ID: `{app.get('approval_id','')}`\n\nProduct: `{app.get('product_id','')}`\n\n## Trace\n\n- Plan: `{app.get('plan_id','')}`\n- Development: `{app.get('dev_run_id','')}`\n- QA: `{app.get('qa_id','')}`\n- Documentation: `{app.get('doc_id','')}`\n\n## QA\n\n- Decision: `{app.get('qa_decision','')}`\n- Score: `{app.get('qa_score','')}`\n",encoding='utf-8'); return p
    def _write_changelog(self, ws, rid, app, ver):
        p=ws/'CHANGELOG_DRAFT.md'; p.write_text(f"# CHANGELOG Draft\n\n## {ver}\n\n- Release `{rid}` generated from approval `{app.get('approval_id','')}`.\n- Product `{app.get('product_id','')}` moved to deploy-ready package.\n",encoding='utf-8'); return p
    def _write_version(self, ws, ver, rid):
        p=ws/'VERSION_CANDIDATE.json'; p.write_text(json.dumps({'version':ver,'release_id':rid,'status':'release_candidate','created':datetime.now().astimezone().isoformat(timespec='seconds')},ensure_ascii=False,indent=2),encoding='utf-8'); return p
    def _write_report(self, ws, rid, app, ver):
        p=ws/'RELEASE_REPORT.md'; p.write_text(f"# Release Report - {rid}\n\n- Version: `{ver}`\n- Approval: `{app.get('approval_id','')}`\n- Product: `{app.get('product_id','')}`\n\nDeploy package created. This MVP does not apply project file changes automatically.\n",encoding='utf-8'); return p
    def _make_package(self, rid, files):
        path=self.package_dir/f'{rid}_RELEASE_PACKAGE.zip'
        if path.exists(): path.unlink()
        with ZipFile(path,'w') as z:
            for f in files: z.write(f, f'{rid}/{f.name}')
        return path
    def _sha256(self,path):
        h=hashlib.sha256()
        with open(path,'rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
        return h.hexdigest()
