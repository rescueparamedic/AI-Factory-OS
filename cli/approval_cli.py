from __future__ import annotations

def register_approval_commands(subparsers):
    p=subparsers.add_parser('approve', help='Approval Gate')
    s=p.add_subparsers(dest='approval_command')
    c=s.add_parser('create', help='최신 또는 지정 문서 결과로 승인 대기 생성'); c.add_argument('--doc', default=None, help='DOC-ID. 생략 시 최신 Documentation 결과 사용')
    sh=s.add_parser('show', help='승인 대기 상세 보기. APP-ID 생략 시 최신 항목'); sh.add_argument('approval_id', nargs='?', default=None, help='APP-ID')
    s.add_parser('latest', help='최신 승인 대기 상세 보기')
    a=s.add_parser('approve', help='승인 처리'); a.add_argument('approval_id', nargs='?', default=None); a.add_argument('--by', default='Owner')
    r=s.add_parser('reject', help='반려 처리'); r.add_argument('approval_id', nargs='?', default=None); r.add_argument('--reason', default='수정 필요'); r.add_argument('--by', default='Owner')
    hist=s.add_parser('history', help='승인/반려 이력'); hist.add_argument('--limit', type=int, default=20)

def _print_approval(item: dict) -> None:
    print('\n=== Approval Gate ===')
    for k in ['approval_id','status','product_id','plan_id','dev_run_id','qa_id','doc_id','qa_decision','qa_score','next_stage','approval_path']:
        print(f'{k:12}: {item.get(k, "")}')
    print('\nDocuments')
    for doc in item.get('documents', []): print(f"- {doc.get('type')} | {doc.get('path')}")
    if item.get('decision_log'):
        print('\nDecision Log')
        for log in item['decision_log']: print(f"- {log.get('timestamp')} | {log.get('action')} | {log.get('by')} | {log.get('reason','')}")

def handle_approval_command(kernel,args)->None:
    if args.approval_command=='create': _print_approval(kernel.create_approval_request(doc_id=args.doc)); return
    if args.approval_command=='latest': _print_approval(kernel.get_latest_approval()); return
    if args.approval_command=='show': _print_approval(kernel.get_approval(args.approval_id)); return
    if args.approval_command=='approve': _print_approval(kernel.approve_request(args.approval_id, by=args.by)); return
    if args.approval_command=='reject': _print_approval(kernel.reject_request(args.approval_id, reason=args.reason, by=args.by)); return
    if args.approval_command=='history':
        items=kernel.list_approval_history(limit=args.limit); print('\n=== Approval History ===')
        if not items: print('승인 이력이 없습니다.'); return
        for item in items: print(f"{item.get('approval_id')} | {item.get('status')} | {item.get('product_id')} | {item.get('decided_at','')}")
        return
    print('approve 하위 명령어가 필요합니다.')
