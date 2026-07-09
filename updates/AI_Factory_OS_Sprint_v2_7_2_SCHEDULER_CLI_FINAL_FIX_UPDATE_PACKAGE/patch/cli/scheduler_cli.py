from __future__ import annotations
import json


def register_scheduler_commands(subparsers):
    parser = subparsers.add_parser("scheduler", help="Task Scheduler & Worker Queue 관리")
    subs = parser.add_subparsers(dest="scheduler_command")

    create = subs.add_parser("enqueue", help="Worker Queue에 작업 추가")
    create.add_argument("--title", required=True)
    create.add_argument("--worker", required=True)
    create.add_argument("--priority", default="medium", choices=["critical", "high", "medium", "low"])
    create.add_argument("--product", default="blog_growth_analyzer")
    create.add_argument("--payload", default="{}", help="JSON payload 문자열")
    create.add_argument("--max-retries", type=int, default=2)

    list_cmd = subs.add_parser("list", help="Queue 작업 목록")
    list_cmd.add_argument("--status", default="all")
    list_cmd.add_argument("--limit", type=int, default=20)

    subs.add_parser("status", help="Scheduler 상태")
    subs.add_parser("next", help="다음 실행 대상 확인")
    subs.add_parser("run-next", help="다음 Queue 작업 1개 실행")
    run_all = subs.add_parser("run-all", help="Queue 작업 여러 개 실행")
    run_all.add_argument("--limit", type=int, default=10)
    run_job = subs.add_parser("run-job", help="특정 Job 실행")
    run_job.add_argument("job_id")


def handle_scheduler_command(kernel, args) -> None:
    if args.scheduler_command == "enqueue":
        try:
            payload = json.loads(args.payload or "{}")
            if not isinstance(payload, dict):
                raise ValueError("payload must be a JSON object")
        except Exception as exc:
            print(f"AI Factory OS scheduler: invalid --payload JSON: {exc}")
            return
        job = kernel.scheduler_enqueue(
            title=args.title,
            worker_id=args.worker,
            payload=payload,
            priority=args.priority,
            product_id=args.product,
            max_retries=args.max_retries,
        )
        print("\n=== Scheduler Job Queued ===")
        _print_job(job)
        return

    if args.scheduler_command == "list":
        jobs = kernel.scheduler_list(status=args.status, limit=args.limit)
        print("\n=== Scheduler Queue ===")
        if not jobs:
            print("No jobs")
            return
        for job in jobs:
            print(f"{job.get('job_id')} | {job.get('priority')} | {job.get('status')} | {job.get('worker_id')} | {job.get('title')}")
        return

    if args.scheduler_command == "status":
        status = kernel.scheduler_status()
        print("\n=== Scheduler Status ===")
        print(f"status     : {status.get('status')}")
        print(f"queue_file : {status.get('queue_file')}")
        print(f"total_jobs : {status.get('total_jobs')}")
        print(f"counts     : {status.get('counts')}")
        if status.get("next_job"):
            print("next_job   : " + status["next_job"].get("job_id", ""))
        return

    if args.scheduler_command == "next":
        job = kernel.scheduler_next()
        print("\n=== Scheduler Next Job ===")
        if not job:
            print("No queued jobs")
        else:
            _print_job(job)
        return

    if args.scheduler_command == "run-next":
        result = kernel.scheduler_run_next()
        print("\n=== Scheduler Run Next ===")
        _print_result(result)
        return

    if args.scheduler_command == "run-all":
        result = kernel.scheduler_run_all(limit=args.limit)
        print("\n=== Scheduler Run All ===")
        print(f"status    : {result.get('status')}")
        print(f"run_count : {result.get('run_count')}")
        return

    if args.scheduler_command == "run-job":
        result = kernel.scheduler_run_job(args.job_id)
        print("\n=== Scheduler Run Job ===")
        _print_result(result)
        return

    print("scheduler 하위 명령어가 필요합니다.")


def _print_job(job):
    print(f"job_id      : {job.get('job_id')}")
    print(f"title       : {job.get('title')}")
    print(f"worker_id   : {job.get('worker_id')}")
    print(f"priority    : {job.get('priority')}")
    print(f"status      : {job.get('status')}")
    print(f"attempts    : {job.get('attempts')}/{job.get('max_retries')}")
    print(f"created_at  : {job.get('created_at')}")


def _print_result(result):
    print(f"status      : {result.get('status')}")
    job = result.get("job") or {}
    if job:
        print(f"job_id      : {job.get('job_id')}")
        print(f"worker_id   : {job.get('worker_id')}")
        print(f"attempts    : {job.get('attempts')}/{job.get('max_retries')}")
        print(f"result_path : {job.get('result_path')}")
    if result.get("error"):
        print(f"error       : {result.get('error')}")
