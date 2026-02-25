# 항공권 가격 트래커 - 스펙 문서

작성일: 2026-02-23

---

## 개요

인천 출발 해외 직항 항공편의 가격을 주기적으로 크롤링하여 최저가를 추적하고, Discord로 브리핑 및 즉시 알림을 발송하는 시스템.

---

## 추적 구간 (Routes)

| 출발 | 도착 | 비고 |
|------|------|------|
| ICN | FUK | 후쿠오카 |
| ICN | NRT | 도쿄 나리타 |
| ICN | HND | 도쿄 하네다 |

- 왕복만 추적
- 직항만 (경유 제외)
- 추후 구간 추가 가능

---

## 날짜 패턴

- **현재 고정**: 금요일 출발 → 일요일 귀국
- **스캔 범위**: 현재 날짜 기준 12주 앞까지
- 추후 다른 패턴 추가 가능하도록 설계

---

## 시간 조건

| 구분 | 조건 |
|------|------|
| 가는 편 (ICN 출발) | 18:00 이후 |
| 오는 편 (목적지 출발) | 16:00 이후 |

- 모든 구간 동일 조건 적용
- 조건 내 모든 시간대 조합을 확인하여 최저가 여정 선택

---

## 크롤링

- **소스**: 네이버 항공권
- **URL 패턴**: `https://flight.naver.com/flights/international/{출발}-{도착}-{YYYYMMDD}/{도착}-{출발}-{YYYYMMDD}?adult=1&fareType=Y`
- **방식**: Playwright headless 브라우저
- **봇 대응**: 요청 간 랜덤 딜레이 (2~5초), User-Agent 설정
- **실패 시**: 1회 재시도 후 포기

---

## 크롤링 주기

- **매 1시간**마다 실행 (cron)
- 1회 실행 시 전체 구간 × 12주치 스캔

---

## 데이터 저장

### DB: SQLite (`flight_tracker.db`)

```sql
CREATE TABLE routes (
  id INTEGER PRIMARY KEY,
  origin TEXT,
  destination TEXT,
  depart_time_from INTEGER DEFAULT 18,
  return_time_from INTEGER DEFAULT 16
);

CREATE TABLE weekly_lowest (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  route_id INTEGER,
  depart_date TEXT,       -- YYYY-MM-DD
  return_date TEXT,       -- YYYY-MM-DD
  min_price INTEGER,      -- 원 단위
  airline TEXT,
  flight_info TEXT,       -- 상세 여정 텍스트
  kal_price INTEGER,      -- 대한항공 가격 (없으면 NULL)
  kal_flight_info TEXT,   -- 대한항공 여정 (없으면 NULL)
  updated_at TEXT         -- ISO8601
);

CREATE TABLE scan_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  route_id INTEGER,
  depart_date TEXT,
  return_date TEXT,
  price INTEGER,
  airline TEXT,
  flight_info TEXT,
  scanned_at TEXT         -- ISO8601
);
```

### 저장 규칙

- 동일 `route_id` + `depart_date` + `return_date` + `price`가 같은 시간(분 단위)에 이미 존재하면 저장 안 함 (중복 방지)
- `weekly_lowest`는 구간 + 날짜 조합별 최저가 1개만 유지
- 최저가 갱신 시 → 즉시 Discord 알림

---

## 알림 / 브리핑

### Discord 채널 ID
`1470680847152840809`

### 정기 브리핑 (KST 기준)
- 매일 **09:00, 13:00, 17:00, 21:00**

### 브리핑 포맷

```
✈️ 항공권 가격 브리핑 | 2026-03-XX 09:00 KST

📍 인천 → 후쿠오카 (직항)
━━━━━━━━━━━━━━━━━━━━
🏆 최저가: 03/27(금) → 03/29(일)
   에어서울 18:30 ICN→20:00 FUK / 17:50 FUK→19:20 ICN
   💰 왕복 473,510원

🇰🇷 대한항공: 03/27(금) → 03/29(일)
   18:40 ICN→20:05 FUK / 16:10 FUK→17:40 ICN
   💰 왕복 590,000원
   (없는 경우 → "해당 시간대 KAL 없음")

📍 인천 → 도쿄 나리타 (직항)
━━━━━━━━━━━━━━━━━━━━
...

📍 인천 → 도쿄 하네다 (직항)
━━━━━━━━━━━━━━━━━━━━
...

📊 다음 브리핑: 13:00 KST
```

### 최저가 갱신 즉시 알림

```
🚨 최저가 갱신! 인천 → 후쿠오카
03/27(금) → 03/29(일)
이전: 520,000원 → 현재: 473,510원 (-8.9%)
항공사: 에어서울
가는 편: 18:30 ICN → 20:00 FUK
오는 편: 17:50 FUK → 19:20 ICN
```

### 대한항공 표시 규칙

- 왕복 **모두** 대한항공인 조합만 표시
- 해당 시간대 대한항공 직항 없으면 → `"해당 시간대 KAL 없음"` 표시

---

## 파일 구조

```
workspace/airplane/
├── SPECIFICATION.md   # 이 파일
├── config.py          # 구간, 시간 설정
├── db.py              # SQLite 헬퍼
├── tracker.py         # 크롤러 + DB 저장 + 즉시 알림
├── briefing.py        # 브리핑 발송
├── requirements.txt
├── README.md
└── flight_tracker.db  # 자동 생성
```

---

## 기술 스택

- Python 3.11+
- `playwright` (async, chromium)
- `aiosqlite`
- `pytz` (KST 처리)
- `subprocess` (openclaw CLI 호출)

### Discord 알림 전송 방법
```bash
openclaw send --channel 1470680847152840809 --message "메시지"
```

---

## Cron 등록 예시

```bash
# 매시간 크롤링
0 * * * * cd /Users/yeon/.openclaw/workspace/airplane && python tracker.py

# 브리핑 (KST = UTC+9)
0 0 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py  # 09:00 KST
0 4 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py  # 13:00 KST
0 8 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py  # 17:00 KST
0 12 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py # 21:00 KST
```

---

## 향후 확장 가능 포인트

- 구간 추가: `config.py`의 `ROUTES` 리스트에 추가
- 날짜 패턴 추가: `config.py`의 `TRIP_PATTERNS`에 추가 (목~일, 금~토 등)
- 알림 기준 커스터마이징: 목표가 설정 기능
- 여러 사이트 지원: 스카이스캐너, 카약 등 크롤러 추가
- 가격 히스토리 그래프 생성
