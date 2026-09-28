# 클라우드 루틴: 유튜브 일일 리포트

- 환경: 트렌드 브리핑 (`env_01NNkpN8f8TUcLfeSNSLw2Ex`, YOUTUBE_API_KEY 설정됨)
- 일정: 매일 08:10 KST (`CRON_TZ=Asia/Seoul 10 8 * * *`)
- 실행 방식: 매 회 새 세션 생성
- 커넥터: Gmail — 등록 도구로는 커넥터를 붙일 수 없어, claude.ai 루틴 화면에서 이 루틴을 열어 Gmail 을 직접 연결해야 함
- 등록됨: trig_014w2KYpvtk8p26f1qzPZku3 (2026-09-28)

## 프롬프트

```
genuinepage/daily-report 저장소에서 유튜브 일일 리포트를 만들어 메일로 보낸다. 무인 실행이니 질문하지 말고 끝까지 스스로 완료할 것. 모든 출력은 한글.

1. 작업 디렉터리에 daily-report 저장소가 없으면 `git clone https://github.com/genuinepage/daily-report` 로 받는다. main 브랜치를 체크아웃하고 최신으로 pull 한 뒤 `python3 run.py` 를 실행한다. YOUTUBE_API_KEY 는 환경변수에 있다. 키 값을 출력·기록하지 않는다.
2. 실행이 성공하면 data/ 와 reports/ 의 변경을 "report: {YYYY-MM-DD}" 메시지로 커밋하고 main 에 푸시한다.
3. reports/{오늘}.html 내용을 본문으로 Gmail 커넥터 send_message 로 발송한다.
   - to: contents@genuineproduction.kr
   - 제목: [유튜브 일일 리포트] {YYYY-MM-DD}
   - htmlBody: reports/{오늘}.html 전체, body: reports/{오늘}.md 전체
   - Gmail 커넥터 도구가 세션에 없으면 발송을 건너뛰고, 푸시 알림에 "메일 미발송(Gmail 커넥터 없음). 리포트는 GitHub reports/{오늘}.md 에 커밋됨" 을 포함한다. 다른 발송 수단을 찾지 않는다.
4. 리포트의 "4. 주의 신호"에 항목이 있으면 푸시 알림에 그 목록만 짧게 보낸다. 없고 메일도 정상 발송됐으면 알림 생략.
5. 수집 실패(API 오류·쿼터 초과 등)면 추측으로 채우지 말고 푸시 알림으로 실패 원인 한 줄만 보고한다. 이때 커밋·메일은 하지 않는다.
```

## 등록 전 확인

- 이 브랜치가 main 에 머지돼 있어야 루틴이 코드를 찾는다.
- 첫 실행 다음 날부터 Δ1일·조회 증가 상위가 채워진다.
