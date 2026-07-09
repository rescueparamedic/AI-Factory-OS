from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json

class ApprovalGate:
    def __init__(self, base_path: Path, documentation_engine, worker_manager, event_bus):
        self.base_path=base_path; self.documentation_engine=documentation_engine; self.worker_manager=worker_manager; self.event_bus=event_bus
        self.queue_dir=base_path/'data'/'approval_queue'; self.history_dir=base_path/'data'/'approval_history'; self.report_dir=base_path/'docs'/'approval'
        self.queue_dir.mkdir(parents=True,exist_ok=True); self.history_dir.mkdir(parents=True,exist_ok=True); self.report_dir.mkdir(parents=True,exist_ok=True)
    def create(self, doc_id: Optional[str]=None)->Dict[str,Any]:
        doc=self._load_doc_result(doc_id); now=datetime.now().astimezone(); aid=f"APP-{now.strftime('%Y%m%d-%H%M%S')}"
        item={'approval_id':aid,'created_at':now.isoformat(timespec='seconds'),'status':'waiting','product_id':doc.get('product_id',''),'plan_id':doc.get('plan_id',''),'dev_run_id':doc.get('dev_run_id',''),'qa_id':doc.get('qa_id',''),'doc_id':doc.get('doc_id',''),'qa_decision':doc.get('qa_decision',''),'qa_score':doc.get('qa_score',''),'documents':doc.get('documents',[]),'decision_log':[],'next_stage':'waiting_owner_decision','release_allowed':False}
        path=self.queue_dir/f'{aid}.json'; item['approval_path']=str(path); path.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
        rep=self._write_approval_report(item); item['report_path']=str(rep); path.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
        self.event_bus.publish('APPROVAL_REQUEST_CREATED',{'approval_id':aid,'doc_id':item['doc_id'],'qa_decision':item['qa_decision']})
        self._audit('APPROVAL_REQUEST_CREATED', aid, 'Documentation result moved to owner approval queue','waiting', item); return item
    def get(self, approval_id: Optional[str]=None)->Dict[str,Any]:
        if not approval_id: return self.latest()
        for d in [self.queue_dir,self.history_dir]:
            p=d/f'{approval_id}.json'
            if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
        raise FileNotFoundError(f'Approval not found: {approval_id}')
    def latest(self)->Dict[str,Any]:
        for d in [self.queue_dir,self.history_dir]:
            files=sorted(d.glob('APP-*.json'), reverse=True)
            if files: return json.loads(files[0].read_text(encoding='utf-8'))
        raise FileNotFoundError('No approval item found.')
    def approve(self, approval_id: Optional[str]=None, by: str='Owner')->Dict[str,Any]:
        item=self.get(approval_id)
        if item.get('status')!='waiting': return item
        now=datetime.now().astimezone(); item.update({'status':'approved','approved_by':by,'approved_at':now.isoformat(timespec='seconds'),'release_allowed':True,'next_stage':'release_ready'})
        item.setdefault('decision_log',[]).append({'timestamp':now.isoformat(timespec='seconds'),'action':'approved','by':by,'reason':'owner approved'})
        self._move_to_history(item); self.event_bus.publish('APPROVAL_APPROVED',{'approval_id':item['approval_id'],'by':by}); self._audit('APPROVAL_APPROVED',item['approval_id'],'Owner approved release candidate','approved',item); return item
    def reject(self, approval_id: Optional[str]=None, reason: str='수정 필요', by: str='Owner')->Dict[str,Any]:
        item=self.get(approval_id)
        if item.get('status')!='waiting': return item
        now=datetime.now().astimezone(); item.update({'status':'rejected','rejected_by':by,'rejected_at':now.isoformat(timespec='seconds'),'reject_reason':reason,'release_allowed':False,'next_stage':'development_revision_required'})
        item.setdefault('decision_log',[]).append({'timestamp':now.isoformat(timespec='seconds'),'action':'rejected','by':by,'reason':reason})
        self._move_to_history(item); self.event_bus.publish('APPROVAL_REJECTED',{'approval_id':item['approval_id'],'by':by,'reason':reason}); self._audit('APPROVAL_REJECTED',item['approval_id'],'Owner rejected release candidate','rejected',item); return item
    def history(self, limit:int=20)->List[Dict[str,Any]]:
        out=[]
        for p in sorted(self.history_dir.glob('APP-*.json'), reverse=True):
            data=json.loads(p.read_text(encoding='utf-8')); out.append({'approval_id':data.get('approval_id',p.stem),'status':data.get('status',''),'product_id':data.get('product_id',''),'decided_at':data.get('approved_at') or data.get('rejected_at') or data.get('created_at','')})
            if len(out)>=limit: break
        return out
    def _load_doc_result(self, doc_id: Optional[str])->Dict[str,Any]:
        if not doc_id: return self.documentation_engine.latest_result()
        p=self.base_path/'data'/'documentation_results'/f'{doc_id}.json'
        if not p.exists(): raise FileNotFoundError(f'Documentation result not found: {doc_id}')
        return json.loads(p.read_text(encoding='utf-8'))
    def _move_to_history(self,item:Dict[str,Any])->None:
        aid=item['approval_id']; q=self.queue_dir/f'{aid}.json'; h=self.history_dir/f'{aid}.json'; item['approval_path']=str(h); h.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8');
        if q.exists(): q.unlink()
    def _write_approval_report(self,item:Dict[str,Any])->Path:
        p=self.report_dir/f"{item['approval_id']}_approval_report.md"; lines=[f"# Approval Report - {item['approval_id']}",'',f"Status: {item.get('status')}",f"Product: {item.get('product_id')}",f"Plan: {item.get('plan_id')}",f"Development Run: {item.get('dev_run_id')}",f"QA: {item.get('qa_id')}",f"Documentation: {item.get('doc_id')}",f"QA Decision: {item.get('qa_decision')}",f"QA Score: {item.get('qa_score')}",'','## Documents','']
        for doc in item.get('documents',[]): lines.append(f"- {doc.get('type')}: `{doc.get('path')}`")
        lines += ['', '## Owner Decision Required', '', '승인 시 Release Engine으로 이동할 수 있습니다.', '반려 시 Development Revision 단계로 되돌아갑니다.']
        p.write_text('\n'.join(lines),encoding='utf-8'); return p
    def _audit(self, action:str, target:str, reason:str, result:str, metadata:Dict[str,Any])->None:
        self.worker_manager.run('audit_log_worker', {'actor':'ApprovalGate','action':action,'target':target,'reason':reason,'result':result,'metadata':{'approval_id':metadata.get('approval_id'),'product_id':metadata.get('product_id'),'plan_id':metadata.get('plan_id'),'qa_id':metadata.get('qa_id'),'doc_id':metadata.get('doc_id'),'status':metadata.get('status')}})
