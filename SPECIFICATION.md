# 항공권 가격 트래커 - 스펙 문서

최종 업데이트: 2026-03-02

---

## 개요

직항 항공편의 가격을 주기적으로 크롤링하여 최저가를 DB에 저장하고, Discord로 브리핑 및 즉시 알림을 발송.  
크롤러 실행 후 `data.json`을 GitHub에 push → Vercel 대시보드가 이를 읽어 가격 추이를 시각화.

---

## 추적 구간

### ROUTES (정기 구간)

| route_id | origin | destination | label | 출발지 |
|----------|--------|-------------|-------|--------|
| 1 | ICN | FUK | 🇯🇵 후쿠오카 | 인천 |
| 2 | ICN | NRT | 🇯🇵 도쿄 나리타 | 인천 |
| 3 | GMP | HND | 🇯🇵 도쿄 하네다 | 김포 |

- 왕복 직항만 추적 (경유 제외)
- 동일 항공사 왕복만 (혼합 항공사 조합 제외)
- 출발: **18:00 이후**, 귀국: **16:00 이후**

### SPECIAL_ROUTES (특별 구간)

| route_id | origin | destination | label | naver 코드 오버라이드 |
|----------|--------|-------------|-------|----------------------|
| 4 | ICN | DPS | 🇮🇩 발리 | origin: `ICN:airport`, dest: `DPS:airport` |
| 5 | ICN | PQC | 🇻🇳 푸꾸옥 | (없음, 기본값) |
| 6 | ICN | HKT | 🇹🇭 푸켓 | origin: `ICN:airport`, dest: `HKT:city` |

- 지정 날짜 쌍만 스캔 (`dates` 필드)
- 시간 제약 없음 (`depart_time_from=0`, `return_time_from=0`)
- `--special-only` 플래그로 SPECIAL_ROUTES만 단독 실행 가능

---

## 날짜 패턴

### TRIP_PATTERNS (ROUTES 적용)
- 금요일 출발 → 일요일 귀국 (2박 3일)
- 스캔 범위: 현재 날짜 기준 **16주** 앞까지

### SPECIAL_DATES (ROUTES 전체 추가 적용)
특정 연휴 등 1회성 날짜 쌍. TRIP_PATTERNS와 합쳐서 스캔.

```python
SPECIAL_DATES = [
    ("20260501", "20260504"),  # 황금연휴 5/1(금)→5/4(월) 3박
    ("20260522", "20260525"),  # 5/22(금)→5/25(월) 3박
]
```

### SPECIAL_ROUTES dates
SPECIAL_ROUTES는 각 라우트 딕셔너리 안의 `dates` 필드로 날짜 직접 지정:
```python
"dates": [("20260501", "20260505")]  # 4박 5일
```

---

## 크롤링

- **소스**: 네이버 항공권
- **URL 패턴**:  
  `https://flight.naver.com/flights/international/{origin}-{dest}-{YYYYMMDD}/{dest}-{origin}-{YYYYMMDD}?adult=1&fareType=Y`
- **naver 코드 오버라이드**: `naver_origin` / `naver_dest` 필드가 있으면 URL에서 공항 코드 대신 사용  
  (예: `ICN:airport`, `HKT:city`)
- **방식**: Playwright headless chromium (async)
- **봇 대응**: 요청 간 랜덤 딜레이 (2~5초), User-Agent 설정
- **재시도**: 최대 1회 후 실패 처리

### 파서 동작
- `HH:MM{ORIGIN}` 출발 패턴으로 항공편 블록 탐지
- 직항 키워드: `직항` (라인 i+2 ~ i+4 검색, +1일 overnight 대응)
- META_KEYWORDS 제외 처리
- 동일 항공사 왕복 조합 필터

### pax3_price (3인 가격 조회)
최저가 확정 후 동일 URL에서 `adult=3` 재조회.

| 값 | 의미 |
|----|------|
| `NULL` | 아직 조회 안 됨 or 스크래핑 실패 |
| `-1` | 해당 날짜/항공사 3석 예약 불가 |
| 양수 | 3인 예약 시 **1인당** 가격 (원) |

---

## 크롤링 주기

- **매시 정각** OpenClaw cron 실행
- 실행 방식: nohup 백그라운드 → cron 쉘은 ~12초 만에 종료, tracker는 계속 실행
- 로그: `/tmp/tracker_{hour}pm.log`
- 1회 실행 시: ROUTES × 16주 + SPECIAL_ROUTES × 지정 날짜 전체 스캔

---

## DB 스키마 (SQLite)

### routes
```sql
CREATE TABLE routes (
  id INTEGER PRIMARY KEY,
  origin TEXT,
  destination TEXT,
  label TEXT,
  depart_time_from INTEGER DEFAULT 18,
  return_time_from INTEGER DEFAULT 16
);
```

### weekly_lowest
구간+날짜 조합별 최저가 1행 유지. 최저가 갱신 시 upsert.
```sql
CREATE TABLE weekly_lowest (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  route_id INTEGER,
  depart_date TEXT,       -- YYYY-MM-DD
  return_date TEXT,
  min_price INTEGER,      -- 원 단위
  airline TEXT,
  flight_info TEXT,       -- 상세 여정 텍스트
  kal_price INTEGER,      -- 대한항공 가격 (없으면 NULL)
  kal_flight_info TEXT,
  updated_at TEXT,        -- ISO8601
  pax3_price INTEGER      -- NULL/-1/양수
);
```

### scan_history
매 크롤링 결과 전체 기록.
```sql
CREATE TABLE scan_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  route_id INTEGER,
  depart_date TEXT,
  return_date TEXT,
  price INTEGER,
  airline TEXT,
  flight_info TEXT,
  scanned_at TEXT
);
```

### price_history / weekly_price_history
시계열 스냅샷 (대시보드 그래프용).

### 데이터 정리 규칙
- `cleanup_past_dates()`: 출발일이 오늘 이전인 `weekly_lowest` 행 삭제; 30일 이상 된 `scan_history` 삭제
- `weekly_lowest` 삭제 권한은 **tracker.py만** 소유 (briefing.py는 삭제 불가)
- 조회 실패 후 재시도도 실패 → 해당 날짜 `weekly_lowest` 행 삭제 (stale 제거)

---

## 데이터 내보내기 (대시보드 연동)

크롤링 완료 후 `export_and_push()` 자동 실행:
1. DB → `dashboard/public/data.json` 생성  
   (구간+날짜당 최근 **200포인트** 제한; DB는 전체 보존)
2. `git add → commit → push` (GitHub: `jrkim3888/airplane_ticket_price_tracker`, main)
3. Vercel이 GitHub에서 data.json을 읽어 대시보드 업데이트

---

## Discord 알림

### 전송 방식
Discord REST API 직접 호출:
```
POST https://discord.com/api/v10/channels/{CHANNEL_ID}/messages
Authorization: Bot {TOKEN}
```
(`openclaw send` 명령은 존재하지 않음 — 직접 API 사용)

### 채널
`1470680847152840809` (mac-mini-channel)  
> ⚠️ 채널이 비공개로 설정된 경우 봇을 채널 퍼미션에 명시적으로 추가해야 함

### 정기 브리핑
KST 기준 **09:00, 13:00, 17:00, 21:00**

브리핑 포맷 예시:
```
✈️ 항공권 가격 브리핑 | 2026-03-02 09:00 KST

🇯🇵 후쿠오카 (ICN → FUK, 직항)
━━━━━━━━━━━━━━━━━━━━
🏆 최저가: 03/27(금) → 03/29(일)
   에어서울 18:30 ICN→20:00 FUK / 17:50 FUK→19:20 ICN
   💰 왕복 473,510원 | 👥 3인: 1인당 458,000원

🇰🇷 대한항공: 03/27(금) → 03/29(일)
   18:40 ICN→20:05 FUK / 16:10 FUK→17:40 ICN
   💰 왕복 590,000원
```

### 즉시 알림 (최저가 갱신 시)
```
🚨 최저가 갱신! 🇯🇵 후쿠오카
03/27(금) → 03/29(일)
이전: 520,000원 → 현재: 473,510원 (-8.9%)
항공사: 에어서울
가는 편: 18:30 ICN → 20:00 FUK
오는 편: 17:50 FUK → 19:20 ICN
```

### 대한항공 표시 규칙
- 왕복 **모두** 대한항공인 조합만 표시
- 없으면 → `"해당 시간대 KAL 없음"`

---

## 웹 대시보드

- **URL**: https://dashboard-eta-amber-70.vercel.app
- **기술**: Next.js (App Router), TypeScript, Tailwind CSS
- **데이터 소스**: `/public/data.json` (크롤러가 push)
- **Vercel 계정**: jrbomini-3567

### 주요 컴포넌트
- `LowestPriceCard`: 구간별 현재 최저가 + 3인 비교 표시
- `WeeklyTable`: 날짜별 가격 테이블 (정렬 버튼, 과거 날짜 필터, 박수 배지)
- 국가 국기: `flagcdn.com/24x18/{cc}.png` img 태그 사용 (Unicode 이모지 대신)

### 배포
코드 변경 후 **반드시 수동 배포** (GitHub push 자동 배포 안 됨):
```bash
cd /Users/yeon/.openclaw/workspace/airplane/dashboard && vercel --prod
```

---

## 핵심 함수 시그니처

```python
# tracker.py
async def main(special_only: bool = False)
def build_url(origin, dest, depart_date, return_date, adults=1, naver_origin=None, naver_dest=None)
async def scan_route(page, route_id, origin, destination, dates, naver_origin=None, naver_dest=None)
def cleanup_past_dates(conn)
def export_and_push()

# briefing.py
async def send_briefing()  # DB 조회 후 Discord 발송; 삭제 불가
```

---

## 기술 스택

- Python 3.11+, `playwright` (async chromium), `aiosqlite`, `pytz`
- Next.js 14 (App Router), TypeScript, Tailwind CSS
- SQLite (WAL mode)
- GitHub (data.json 중계), Vercel (ISR)

---

## 향후 확장 포인트

- 구간 추가: `config.py` ROUTES / SPECIAL_ROUTES에 항목 추가
- 날짜 패턴 추가: TRIP_PATTERNS 또는 SPECIAL_DATES 활용
- 목표가 알림: 특정 가격 이하 시 즉시 알림
- 추가 항공권 사이트 지원 (스카이스캐너 등)
- 가격 히스토리 그래프 (대시보드 확장)
