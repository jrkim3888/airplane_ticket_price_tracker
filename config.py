"""항공권 가격 트래커 - 설정"""

# 추적 구간 (Routes)
ROUTES = [
    {"origin": "ICN", "destination": "FUK", "label": "후쿠오카"},
    {"origin": "ICN", "destination": "NRT", "label": "도쿄 나리타"},
    {"origin": "GMP", "destination": "HND", "label": "도쿄 하네다"},
]

# 시간 조건
DEPART_TIME_FROM = 18   # 가는 편: ICN 출발 18:00 이후
RETURN_TIME_FROM = 16   # 오는 편: 목적지 출발 16:00 이후

# 날짜 패턴 (출발 요일, 귀국 요일)
# weekday: 0=월 ~ 6=일
TRIP_PATTERNS = [
    {"name": "금-일", "depart_weekday": 4, "return_weekday": 6},
]

# 스캔 범위 (주)
SCAN_WEEKS = 16

# 네이버 항공권 URL 패턴
NAVER_FLIGHT_URL = (
    "https://flight.naver.com/flights/international/"
    "{origin}-{destination}-{depart_date}/{destination}-{origin}-{return_date}"
    "?adult=1&fareType=Y"
)

# 봇 대응
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5
MAX_RETRIES = 1

# Discord 채널
DISCORD_CHANNEL_ID = "1470680847152840809"

# DB 파일 경로
import os
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flight_tracker.db")

# 브리핑 시간 (KST)
BRIEFING_HOURS_KST = [9, 13, 17, 21]
