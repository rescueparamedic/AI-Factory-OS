# User Guide Draft

## 목적

이 문서는 QA 결과 `QA-20260629-220841` 기반으로 생성된 사용자 가이드 초안입니다.

## 사용 흐름

```powershell
python main.py plan create --request "요청 내용"
python main.py dev run
python main.py qa run
python main.py docs run
```

## 다음 단계

Approval Gate에서 사용자가 변경 내용을 승인하면 Release Engine으로 이동합니다.
