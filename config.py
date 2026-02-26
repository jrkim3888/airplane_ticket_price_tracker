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

# 특별 일정 (반복 패턴 외 1회성 날짜 쌍 — 기존 ROUTES 전체에 적용)
SPECIAL_DATES = [
    ("20260501", "20260504"),  # 황금연휴 5/1(금)→5/4(월)
]

# 특별 구간 (구간+날짜 세트 — 단기 트래킹용, 시간 제약 없음)
# 만료 후 weekly_lowest가 비면 대시보드에서 자동으로 사라짐 (B안)
SPECIAL_ROUTES = [
    {
        "origin": "ICN", "destination": "DPS", "label": "발리",
        "depart_time_from": 0, "return_time_from": 0,
        "dates": [("20260502", "20260505")],
    },
    {
        "origin": "ICN", "destination": "PQC", "label": "푸꾸옥",
        "depart_time_from": 0, "return_time_from": 0,
        "dates": [("20260502", "20260505")],
    },
    {
        "origin": "ICN", "destination": "HKT", "label": "푸켓",
        "depart_time_from": 0, "return_time_from": 0,
        "dates": [("20260502", "20260505")],
    },
]

# 전체 구간 (DB route_id 순서 기준)
ALL_ROUTES = ROUTES + SPECIAL_ROUTES

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
