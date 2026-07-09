# AI Factory OS Sprint v2.7.2 적용 방법

## 1. ZIP 저장 위치
다운로드한 ZIP 파일을 아래 폴더에 저장합니다.

```text
C:\AIFactory\AI Factory OS\updates\
```

## 2. 압축 해제
ZIP을 압축 해제하면 다음 구조가 보입니다.

```text
patch
CHANGELOG.md
README.md
```

## 3. patch 내용 복사
`patch` 폴더를 열고, 그 안의 모든 파일과 폴더를 선택합니다.

```text
Ctrl + A
Ctrl + C
```

## 4. 프로젝트 루트에 붙여넣기
아래 폴더에 붙여넣습니다.

```text
C:\AIFactory\AI Factory OS\
```

즉, `main.py`가 있는 폴더입니다.

같은 이름의 파일이 있다고 나오면 **대상 파일로 바꾸기/덮어쓰기**를 선택합니다.

## 5. 테스트 명령
PowerShell 또는 VS Code Terminal에서 실행합니다.

```powershell
cd "C:\AIFactory\AI Factory OS"
python main.py -h
```

정상이라면 명령 목록에 `scheduler`가 보여야 합니다.

그다음 아래 명령을 순서대로 실행합니다.

```powershell
python main.py scheduler status
python main.py scheduler enqueue --title "v2.7.2 Scheduler Final 테스트" --worker markdown_worker --priority high --payload '{"filename":"docs/operations/v2_7_2_scheduler_final_test.md","title":"v2.7.2 Scheduler Final Test","body":["Scheduler final package completed"]}'
python main.py scheduler next
python main.py scheduler run-next
python main.py scheduler list --limit 5
python main.py dashboard live-build
```

## 6. 정상 기대 결과

- `python main.py -h` 결과에 `scheduler` 표시
- `scheduler status` 결과에 `status : available`
- `scheduler enqueue` 결과에 `Scheduler Job Queued`
- `scheduler run-next` 결과에 `status : completed`
- `dashboard live-build` 결과에 `status : completed`

## 7. 캡처해서 전달할 화면

아래 결과가 보이는 터미널 화면을 캡처해서 전달하면 됩니다.

```text
scheduler status
scheduler run-next
dashboard live-build
```
