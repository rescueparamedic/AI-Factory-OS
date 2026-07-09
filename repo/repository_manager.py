from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json


class RepositoryManager:
    """
    Sprint 10-3 MVP.
    GitHub 자동 연동 전 단계로, 현재 AI Factory OS 폴더가
    정식 저장소로 운영 가능한 상태인지 점검하고 가이드/스냅샷을 생성한다.
    """

    REQUIRED_ROOT_FILES = [
        "main.py",
        "README.md",
        "requirements.txt",
        "VERSION.json",
    ]

    REQUIRED_DIRS = [
        "cli",
        "os_core",
        "agents",
        "teams",
        "workers",
        "managers",
        "runtime",
        "update",
        "doctor",
        "products",
        "data",
        "docs",
        "updates",
        "repo",
    ]

    RECOMMENDED_FILES = [
        ".gitignore",
        "CHANGELOG.md",
        "PROJECT_STATUS.md",
        "MASTER_INDEX.md",
    ]

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.docs_dir = base_path / "docs" / "repository"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = base_path / "data" / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def status(self) -> Dict[str, Any]:
        checks: List[Dict[str, str]] = []

        git_enabled = (self.base_path / ".git").exists()

        for rel in self.REQUIRED_ROOT_FILES:
            path = self.base_path / rel
            checks.append({
                "name": f"required_file:{rel}",
                "status": "OK" if path.is_file() else "FAIL",
                "message": "exists" if path.is_file() else "missing",
            })

        for rel in self.REQUIRED_DIRS:
            path = self.base_path / rel
            checks.append({
                "name": f"required_dir:{rel}",
                "status": "OK" if path.is_dir() else "FAIL",
                "message": "exists" if path.is_dir() else "missing",
            })

        for rel in self.RECOMMENDED_FILES:
            path = self.base_path / rel
            checks.append({
                "name": f"recommended_file:{rel}",
                "status": "OK" if path.is_file() else "WARN",
                "message": "exists" if path.is_file() else "recommended but missing",
            })

        failures = [c for c in checks if c["status"] == "FAIL"]
        warnings = [c for c in checks if c["status"] == "WARN"]

        if failures:
            health = "CHECK_REQUIRED"
        elif warnings:
            health = "GOOD_WITH_WARNINGS"
        else:
            health = "HEALTHY"

        return {
            "project_path": str(self.base_path),
            "git_enabled": git_enabled,
            "mode": "git_repository" if git_enabled else "local_project",
            "health": health,
            "checks": checks,
        }

    def create_guide(self) -> Dict[str, Any]:
        path = self.docs_dir / "GITHUB_OPERATION_GUIDE.md"
        content = """# AI Factory OS GitHub Operation Guide

## 목적

AI Factory OS를 ZIP 덮어쓰기 방식이 아닌 정식 Python 프로젝트 저장소로 운영하기 위한 가이드입니다.

## 권장 브랜치

```text
main      : 항상 실행 가능한 안정 버전
develop   : Sprint 개발 브랜치
sprint/*  : 개별 Sprint 작업 브랜치
```

## 권장 흐름

```text
1. 현재 안정 버전 백업
2. update install로 패치 적용
3. doctor 실행
4. smoke test 실행
5. Git commit
6. develop 반영
7. 안정화 후 main 병합
```

## 기본 명령

```powershell
git init
git status
git add .
git commit -m "Sprint 10-3 repository mode"
git branch -M main
```

## 주의

- API Key, 개인정보, 대용량 백업 파일은 Git에 올리지 않습니다.
- backups/, data/audit/, data/worker_results/ 등은 운영 로그 성격이 강하므로 기본적으로 제외하는 것을 권장합니다.
- main 브랜치는 사용자 승인 없이 병합하지 않습니다.
```
"""
        path.write_text(content, encoding="utf-8")
        return {
            "status": "completed",
            "path": str(path),
        }

    def create_snapshot(self) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"REPOSITORY_SNAPSHOT_{now}.json"

        files = []
        dirs = []

        excluded_parts = {"backups", "__pycache__", ".git"}

        for item in self.base_path.rglob("*"):
            rel_parts = set(item.relative_to(self.base_path).parts)
            if rel_parts & excluded_parts:
                continue

            rel = str(item.relative_to(self.base_path)).replace("\\", "/")
            if item.is_dir():
                dirs.append(rel)
            elif item.is_file():
                files.append(rel)

        data = {
            "snapshot_id": f"SNAP-{now}",
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "project_path": str(self.base_path),
            "file_count": len(files),
            "dir_count": len(dirs),
            "files": sorted(files),
            "dirs": sorted(dirs),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "status": "completed",
            "path": str(path),
            "file_count": len(files),
            "dir_count": len(dirs),
        }
