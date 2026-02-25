# 항공권 가격 트래커

인천 출발 해외 직항 항공편의 가격을 주기적으로 크롤링하여 최저가를 추적하고, Discord로 브리핑 및 즉시 알림을 발송하는 시스템.

## 추적 구간

| 출발 | 도착 | 비고 |
|------|------|------|
| ICN | FUK | 후쿠오카 |
| ICN | NRT | 도쿄 나리타 |
| ICN | HND | 도쿄 하네다 |

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

## 실행

### 크롤링 (수동)
```bash
python tracker.py
```

### 브리핑 발송 (수동)
```bash
python briefing.py
```

### Cron 등록

```bash
# 매시간 크롤링
0 * * * * cd /Users/yeon/.openclaw/workspace/airplane && python tracker.py

# 브리핑 (KST = UTC+9)
0 0 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py  # 09:00 KST
0 4 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py  # 13:00 KST
0 8 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py  # 17:00 KST
0 12 * * * cd /Users/yeon/.openclaw/workspace/airplane && python briefing.py # 21:00 KST
```

## 파일 구조

| 파일 | 역할 |
|------|------|
| `config.py` | 구간, 시간, 설정 |
| `db.py` | SQLite 헬퍼 |
| `tracker.py` | 크롤러 + DB 저장 + 즉시 알림 |
| `briefing.py` | 브리핑 발송 |
| `flight_tracker.db` | 자동 생성 DB |

## 구간 추가

`config.py`의 `ROUTES` 리스트에 추가:

```python
ROUTES = [
    {"origin": "ICN", "destination": "FUK", "label": "후쿠오카"},
    {"origin": "ICN", "destination": "NRT", "label": "도쿄 나리타"},
    {"origin": "ICN", "destination": "HND", "label": "도쿄 하네다"},
    {"origin": "ICN", "destination": "KIX", "label": "오사카"},  # 추가
]
```
