from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AIReviewResult:
    status: str
    score: int
    summary: str
    risks: list[str]
    raw: Dict[str, Any]


class AIReviewClient:
    def __init__(self, provider: str = 'gemini', api_key: str | None = None, model: str = 'gemini-2.5-flash'):
        self.provider = provider
        self.api_key = api_key
        self.model = model

    def review_blog_post(self, title: str, body: str, keyword: str = '') -> AIReviewResult:
        if not self.api_key:
            return AIReviewResult(status='fallback', score=0, summary='API Key가 없어 외부 검수를 실행하지 않았습니다.', risks=['api_key_missing'], raw={})
        return AIReviewResult(status='draft_not_connected', score=0, summary='검수 클라이언트 초안입니다. 실제 API 연결은 승인 후 진행합니다.', risks=['adapter_not_implemented'], raw={'provider': self.provider, 'model': self.model})
