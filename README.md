# 항공권 가격 트래커

직항 항공편 최저가를 주기적으로 크롤링하여 DB에 저장하고, Discord로 브리핑 및 즉시 알림을 발송하는 시스템.  
Vercel에 배포된 웹 대시보드에서 가격 추이를 확인할 수 있습니다.

**대시보드**: https://dashboard-eta-amber-70.vercel.app

---

## 추적 구간

### 정기 구간 (ROUTES) — 매주 금→일 패턴 + 특별 일정

| route_id | 출발 | 도착 | 출발지 | 비고 |
|----------|------|------|--------|------|
| 1 | ICN | FUK | 인천 | 🇯🇵 후쿠오카 |
| 2 | ICN | NRT | 인천 | 🇯🇵 도쿄 나리타 |
| 3 | GMP | HND | 김포 | 🇯🇵 도쿄 하네다 |

### 특별 구간 (SPECIAL_ROUTES) — 지정 날짜만, 시간 제약 없음

| route_id | 출발 | 도착 | 비고 | 트래킹 기간 |
|----------|------|------|------|-------------|
| 4 | ICN | DPS | 🇮🇩 발리 | 2026/05/01→05/05 |
| 5 | ICN | PQC | 🇻🇳 푸꾸옥 | 2026/05/01→05/05 |
| 6 | ICN | HKT | 🇹🇭 푸켓 | 2026/05/01→05/05 |

---

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

---

## 실행

### 전체 크롤링 (수동)
```bash
python tracker.py
```

### SPECIAL_ROUTES만 크롤링
```bash
python tracker.py --special-only
```

### 브리핑 발송 (수동)
```bash
python briefing.py
```

---

## Cron (OpenClaw 관리)

크론은 **OpenClaw cron**으로 등록되어 있습니다 (시스템 crontab 아님).

| 작업 | 스케줄 | 설명 |
|------|--------|------|
| 크롤러 | `0 * * * *` | 매시 정각, nohup 백그라운드 실행 |
| 브리핑 | `0 9,13,17,21 * * *` | KST 기준 9/13/17/21시 |

크롤러는 실행 후 즉시 쉘이 종료되고 (`nohup` 패턴) 백그라운드에서 계속 동작합니다.  
로그: `/tmp/tracker_{hour}pm.log`

---

## 파일 구조

```
workspace/airplane/
├── config.py            # 구간, 날짜 패턴, 시간 조건 설정
├── db.py                # SQLite 헬퍼 (초기화, CRUD)
├── tracker.py           # 크롤러 + DB 저장 + Discord 즉시 알림
├── briefing.py          # 정기 브리핑 발송
├── requirements.txt
├── README.md
├── SPECIFICATION.md     # 상세 스펙
├── flight_tracker.db    # SQLite DB (자동 생성)
└── dashboard/           # Vercel 웹 대시보드 (Next.js)
    ├── app/
    ├── components/
    ├── public/data.json  # 크롤러가 매 실행 후 업데이트
    └── ...
```

---

## 구간 추가

### 정기 구간 추가
`config.py`의 `ROUTES` 리스트에 추가:
```python
{"origin": "ICN", "destination": "KIX", "label": "🇯🇵 오사카"},
```

### 특별 구간 추가 (단기 추적)
`config.py`의 `SPECIAL_ROUTES` 리스트에 추가:
```python
{
    "origin": "ICN", "destination": "BKK", "label": "🇹🇭 방콕",
    "depart_time_from": 0, "return_time_from": 0,
    "dates": [("20260501", "20260505")],
},
```
네이버 URL에서 공항 코드 포맷이 다른 경우 `naver_origin` / `naver_dest` 오버라이드 사용.

---

## 대시보드 배포

대시보드 코드 변경 후 **반드시 수동 배포** 필요 (GitHub push만으로는 자동 배포 안 됨):

```bash
cd /Users/yeon/.openclaw/workspace/airplane/dashboard && vercel --prod
```
