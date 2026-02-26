"""항공권 가격 트래커 - 크롤러 + DB 저장 + 즉시 알림"""

import asyncio
import random
import re
import subprocess
import urllib.request
import urllib.error
import json as _json
import ssl as _ssl
import logging
from datetime import datetime, timedelta

import pytz
from playwright.async_api import async_playwright

from config import (
    ROUTES, TRIP_PATTERNS, SCAN_WEEKS, SPECIAL_DATES,
    NAVER_FLIGHT_URL, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX, MAX_RETRIES,
    DISCORD_CHANNEL_ID, DEPART_TIME_FROM, RETURN_TIME_FROM,
)
from db import (init_db, get_db, insert_scan, update_weekly_lowest,
                insert_price_snapshot, insert_weekly_price_snapshot)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

KST = pytz.timezone("Asia/Seoul")

DESTINATION_LABELS = {r["destination"]: r["label"] for r in ROUTES}


def generate_scan_dates() -> list[tuple[str, str]]:
    """금요일 출발 → 일요일 귀국, 12주치 날짜 쌍을 생성한다."""
    today = datetime.now(KST).date()
    dates = []

    for pattern in TRIP_PATTERNS:
        depart_wd = pattern["depart_weekday"]
        return_wd = pattern["return_weekday"]
        trip_length = (return_wd - depart_wd) % 7

        # 가장 가까운 출발 요일 찾기
        days_ahead = (depart_wd - today.weekday()) % 7
        if days_ahead == 0 and today.weekday() == depart_wd:
            # 오늘이 출발 요일이면 포함
            next_depart = today
        else:
            next_depart = today + timedelta(days=days_ahead)

        # 이미 지난 날짜면 다음 주로
        if next_depart < today:
            next_depart += timedelta(days=7)

        for week in range(SCAN_WEEKS):
            depart = next_depart + timedelta(weeks=week)
            ret = depart + timedelta(days=trip_length)
            dates.append((depart.strftime("%Y%m%d"), ret.strftime("%Y%m%d")))

    # 특별 일정 추가 (과거 날짜 제외, 중복 제외)
    existing = set(dates)
    for dep, ret in SPECIAL_DATES:
        from datetime import date
        dep_date = date(int(dep[:4]), int(dep[4:6]), int(dep[6:]))
        if dep_date >= today and (dep, ret) not in existing:
            dates.append((dep, ret))

    return dates


def build_url(origin: str, destination: str, depart_date: str, return_date: str,
              adults: int = 1) -> str:
    url = NAVER_FLIGHT_URL.format(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
    )
    if adults != 1:
        url = url.replace("adult=1", f"adult={adults}")
    return url


_token_result = subprocess.run(
    ["openclaw", "config", "get", "channels.discord.token"],
    capture_output=True, text=True
)
DISCORD_BOT_TOKEN = _token_result.stdout.strip()


def send_discord(message: str):
    """Discord REST API로 메시지를 전송한다."""
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
    payload = _json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "mc-mini-flight-tracker/1.0",
        },
        method="POST",
    )
    ssl_ctx = _ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = _ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            if resp.status in (200, 201):
                logger.info("Discord 알림 전송 완료")
            else:
                logger.error(f"Discord 전송 실패: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        logger.error(f"Discord 전송 실패: HTTP {e.code} {e.read().decode()}")
    except Exception as e:
        logger.error(f"Discord 전송 실패: {e}")


def format_price_alert(destination: str, depart_date: str, return_date: str,
                       old_price, new_price: int, airline: str, flight_info: str,
                       overall_min: int | None = None,
                       overall_min_date: str | None = None) -> str:
    """최저가 갱신 즉시 알림 메시지를 생성한다."""
    label = DESTINATION_LABELS.get(destination, destination)
    dd = datetime.strptime(depart_date, "%Y-%m-%d")
    rd = datetime.strptime(return_date, "%Y-%m-%d")
    weekdays_kr = ["월", "화", "수", "목", "금", "토", "일"]
    dd_str = f"{dd.month:02d}/{dd.day:02d}({weekdays_kr[dd.weekday()]})"
    rd_str = f"{rd.month:02d}/{rd.day:02d}({weekdays_kr[rd.weekday()]})"

    lines = [f"🚨 최저가 갱신! 인천 → {label}"]
    lines.append(f"📅 {dd_str} → {rd_str}")

    if old_price is not None:
        diff_pct = (new_price - old_price) / old_price * 100
        lines.append(f"이전: {old_price:,}원 → 현재: {new_price:,}원 ({diff_pct:+.1f}%)")
    else:
        lines.append(f"현재: {new_price:,}원")

    lines.append(f"항공사: {airline}")

    # flight_info에서 가는 편/오는 편 파싱
    if " / " in flight_info:
        out_leg, ret_leg = flight_info.split(" / ", 1)
        lines.append(f"↗ 가는편: {out_leg.strip()}")
        lines.append(f"↙ 오는편: {ret_leg.strip()}")
    else:
        lines.append(flight_info)

    # 전체 최저가 표시
    if overall_min is not None:
        if overall_min_date:
            omd = datetime.strptime(overall_min_date, "%Y-%m-%d")
            omd_str = f"{omd.month:02d}/{omd.day:02d}({weekdays_kr[omd.weekday()]})"
            lines.append(f"📊 구간 전체 최저가: {overall_min:,}원 ({omd_str} 출발)")
        else:
            lines.append(f"📊 구간 전체 최저가: {overall_min:,}원")

    return "\n".join(lines)


def parse_naver_flights(text: str, origin: str, destination: str,
                        depart_time_from: int, return_time_from: int) -> dict | None:
    """main 요소의 innerText를 줄 단위로 파싱하여 항공편 정보를 추출한다.

    항공사명 → (이벤트혜택?) → HH:MMICN → HH:MMDEST → 직항, ... 패턴을 찾되
    가는 편/오는 편 항공사가 다른 조합(혼합 예약)도 처리한다.

    Returns:
        {
            "min_price": int,
            "airline": str,
            "flight_info": str,
            "kal_price": int | None,
            "kal_flight_info": str | None,
        }
    """
    # 항공사명으로 잘못 인식하면 안 되는 메타 라인
    META_KEYWORDS = {"이벤트혜택", "공동운항", "동일가", "특가확인", "알림받기"}

    def is_meta(s: str) -> bool:
        return any(kw in s for kw in META_KEYWORDS) or s.strip() in {"할인", " 할인"}

    def is_airline_name(s: str) -> bool:
        if is_meta(s):
            return False
        if re.search(r"\d", s):
            return False
        if not re.match(r"^[가-힣a-zA-Z\s·,]+$", s):
            return False
        return 2 <= len(s) <= 30

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    depart_out_pat = re.compile(rf"\d{{2}}:\d{{2}}{re.escape(origin)}")
    depart_ret_pat = re.compile(rf"\d{{2}}:\d{{2}}{re.escape(destination)}")

    results = []
    i = 0
    while i < len(lines):
        # 가는 편 출발 패턴: HH:MMICN
        if not depart_out_pat.match(lines[i]):
            i += 1
            continue

        # lines[i]   = HH:MMICN (가는 편 출발)
        # lines[i+1] = HH:MMDEST (가는 편 도착)
        # lines[i+2] = "직항, ..." or "경유..."
        if i + 2 >= len(lines):
            i += 1
            continue

        depart_hour = int(lines[i][:2])
        is_out_direct = "직항" in lines[i + 2] and "경유" not in lines[i + 2]

        if not is_out_direct:
            i += 1
            continue

        # 가는 편 직항 확인. 오는 편 출발 HH:MMDEST 탐색 (다음 15줄 내)
        ret_start = None
        for j in range(i + 3, min(i + 18, len(lines))):
            if depart_ret_pat.match(lines[j]):
                if j + 2 < len(lines) and "직항" in lines[j + 2] and "경유" not in lines[j + 2]:
                    ret_start = j
                    break

        if ret_start is None:
            i += 1
            continue

        return_hour = int(lines[ret_start][:2])

        # 시간 조건 체크
        if depart_hour < depart_time_from or return_hour < return_time_from:
            i += 1
            continue

        # 항공사: lines[i] 이전을 역방향으로 탐색 (메타 라인 건너뜀)
        airline = "기타"
        for k in range(i - 1, max(i - 6, -1), -1):
            if is_airline_name(lines[k]):
                airline = lines[k]
                break

        # 동일 항공사 왕복 필터: 가는 편 도착(i+1)과 오는 편 출발(ret_start) 사이에
        # 다른 항공사명이 있으면 혼합 조합 → 스킵
        is_mixed = False
        for k in range(i + 3, ret_start):
            if is_airline_name(lines[k]) and lines[k] != airline:
                is_mixed = True
                break
        if is_mixed:
            i += 1
            continue

        # 가격 찾기: 오는 편 직항 줄 이후 15줄 내에서 "왕복 XXX원" 패턴
        price = None
        for j in range(ret_start + 3, min(ret_start + 18, len(lines))):
            m = re.search(r"왕복\s*([\d,]+)원", lines[j])
            if m:
                price = int(m.group(1).replace(",", ""))
                break

        if not price:
            i += 1
            continue

        flight_info = (
            f"{lines[i][:5]} {origin}→{destination} {lines[i+1][:5]} / "
            f"{lines[ret_start][:5]} {destination}→{origin} {lines[ret_start+1][:5]}"
        )
        results.append({
            "airline": airline,
            "price": price,
            "flight_info": flight_info,
        })

        i = ret_start + 3  # 다음 항목으로

    if not results:
        return None

    # 최저가 찾기
    best = min(results, key=lambda x: x["price"])

    # KAL 찾기 (왕복 모두 대한항공인 조합 — 항공사명에 "대한항공" 포함)
    kal = next((r for r in results if "대한항공" in r["airline"]), None)

    return {
        "min_price": best["price"],
        "airline": best["airline"],
        "flight_info": best["flight_info"],
        "kal_price": kal["price"] if kal else None,
        "kal_flight_info": kal["flight_info"] if kal else None,
    }


async def scrape_flights(page, url: str, origin: str, destination: str,
                         depart_time_from: int, return_time_from: int) -> dict | None:
    """네이버 항공권 페이지에서 항공편 정보를 크롤링한다."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)

        text = await page.evaluate(
            '() => { const m = document.querySelector("main"); return m ? m.innerText : ""; }'
        )

        if not text or len(text) < 100:
            logger.warning(f"텍스트 추출 실패 또는 내용 부족: {url}")
            return None

        return parse_naver_flights(text, origin, destination, depart_time_from, return_time_from)

    except Exception as e:
        logger.error(f"크롤링 오류 ({url}): {e}")
        return None


async def scan_route(page, route_id: int, origin: str, destination: str,
                     dates: list[tuple[str, str]]):
    """한 구간의 전체 날짜를 스캔한다."""
    db = await get_db()
    try:
        route_cursor = await db.execute(
            "SELECT depart_time_from, return_time_from FROM routes WHERE id = ?",
            (route_id,),
        )
        route_row = await route_cursor.fetchone()
        depart_time_from = route_row[0] if isinstance(route_row, tuple) else route_row["depart_time_from"]
        return_time_from = route_row[1] if isinstance(route_row, tuple) else route_row["return_time_from"]

        for depart_date, return_date in dates:
            url = build_url(origin, destination, depart_date, return_date)
            dd_fmt = f"{depart_date[:4]}-{depart_date[4:6]}-{depart_date[6:]}"
            rd_fmt = f"{return_date[:4]}-{return_date[4:6]}-{return_date[6:]}"
            logger.info(f"스캔: {origin}→{destination} {dd_fmt} ~ {rd_fmt}")

            result = None
            for attempt in range(MAX_RETRIES + 1):
                result = await scrape_flights(
                    page, url, origin, destination,
                    depart_time_from, return_time_from,
                )
                if result is not None:
                    break
                if attempt < MAX_RETRIES:
                    logger.info(f"재시도 ({attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(2)

            if result is None:
                logger.warning(f"결과 없음: {origin}→{destination} {dd_fmt}")
                # 기존 weekly_lowest 데이터가 있으면 삭제 (크롤러가 데이터 관리 담당)
                existing = await db.execute(
                    "SELECT id FROM weekly_lowest WHERE route_id=? AND depart_date=? AND return_date=?",
                    (route_id, dd_fmt, rd_fmt)
                )
                if await existing.fetchone():
                    await db.execute(
                        "DELETE FROM weekly_lowest WHERE route_id=? AND depart_date=? AND return_date=?",
                        (route_id, dd_fmt, rd_fmt)
                    )
                    await db.commit()
                    logger.info(f"weekly_lowest 삭제: {origin}→{destination} {dd_fmt} (항공편 소멸)")
                await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
                continue

            now = datetime.now(KST).isoformat()

            # scan_history 저장
            await insert_scan(
                db, route_id, dd_fmt, rd_fmt,
                result["min_price"], result["airline"],
                result["flight_info"], now,
            )

            # weekly_lowest 갱신
            price_change = await update_weekly_lowest(
                db, route_id, dd_fmt, rd_fmt,
                result["min_price"], result["airline"], result["flight_info"],
                result["kal_price"], result["kal_flight_info"], now,
            )

            await db.commit()

            # 최저가 갱신 시 즉시 알림
            if price_change is not None:
                old_price, new_price = price_change
                if old_price is not None:  # 기존 대비 갱신된 경우만 알림
                    # 해당 구간 전체 최저가 조회
                    overall_row = await db.execute(
                        "SELECT MIN(min_price) as p, depart_date FROM weekly_lowest WHERE route_id=?",
                        (route_id,)
                    )
                    overall = await overall_row.fetchone()
                    overall_min = overall["p"] if overall else None
                    overall_min_date = overall["depart_date"] if overall else None

                    alert_msg = format_price_alert(
                        destination, dd_fmt, rd_fmt,
                        old_price, new_price,
                        result["airline"], result["flight_info"],
                        overall_min=overall_min,
                        overall_min_date=overall_min_date,
                    )
                    send_discord(alert_msg)

            # 랜덤 딜레이
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            await asyncio.sleep(delay)

    finally:
        await db.close()


async def cleanup_past_dates():
    """오늘 이전 날짜의 weekly_lowest 행을 삭제하고, 30일 이상 된 scan_history를 정리한다."""
    db = await get_db()
    today_str = datetime.now(KST).date().isoformat()  # "YYYY-MM-DD"
    cutoff_str = (datetime.now(KST).date() - timedelta(days=30)).isoformat()
    try:
        # weekly_lowest 과거 날짜 삭제
        cursor = await db.execute(
            "SELECT COUNT(*) FROM weekly_lowest WHERE depart_date < ?",
            (today_str,)
        )
        count = (await cursor.fetchone())[0]
        if count > 0:
            await db.execute(
                "DELETE FROM weekly_lowest WHERE depart_date < ?",
                (today_str,)
            )
            logger.info(f"weekly_lowest 과거 날짜 {count}건 삭제 (< {today_str})")
        else:
            logger.info("삭제할 weekly_lowest 과거 날짜 없음")

        # scan_history 30일 이상 된 데이터 삭제
        cursor2 = await db.execute(
            "SELECT COUNT(*) FROM scan_history WHERE scanned_at < ?",
            (cutoff_str,)
        )
        count2 = (await cursor2.fetchone())[0]
        if count2 > 0:
            await db.execute(
                "DELETE FROM scan_history WHERE scanned_at < ?",
                (cutoff_str,)
            )
            logger.info(f"scan_history 30일+ 데이터 {count2}건 삭제 (< {cutoff_str})")

        await db.commit()
    finally:
        await db.close()


async def check_pax3_prices(page):
    """구간별 전체 최저가 주를 adult=3으로 크롤링해 pax3_price를 갱신한다."""
    db = await get_db()
    try:
        for i, route in enumerate(ROUTES, start=1):
            origin = route["origin"]
            destination = route["destination"]
            depart_time_from = route.get("depart_time_from", DEPART_TIME_FROM)
            return_time_from = route.get("return_time_from", RETURN_TIME_FROM)

            # 해당 구간의 현재 최저가 주 조회
            row = await db.execute(
                "SELECT depart_date, return_date, min_price FROM weekly_lowest "
                "WHERE route_id = ? ORDER BY min_price ASC LIMIT 1",
                (i,)
            )
            best = await row.fetchone()
            if not best:
                continue

            dep = best["depart_date"].replace("-", "")
            ret = best["return_date"].replace("-", "")
            url = build_url(origin, destination, dep, ret, adults=3)

            logger.info(f"3인 가격 체크: {origin}→{destination} {best['depart_date']} (adult=3)")
            result = await scrape_flights(page, url, origin, destination,
                                         depart_time_from, return_time_from)
            await asyncio.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

            pax3_price = result["min_price"] if result else None
            await db.execute(
                "UPDATE weekly_lowest SET pax3_price = ? "
                "WHERE route_id = ? AND depart_date = ? AND return_date = ?",
                (pax3_price, i, best["depart_date"], best["return_date"])
            )
            if pax3_price is not None:
                logger.info(f"3인 1인당: {pax3_price:,}원 (1인: {best['min_price']:,}원)")
            else:
                logger.warning(f"3인 가격 조회 실패: {origin}→{destination} {best['depart_date']}")

        await db.commit()
    finally:
        await db.close()


async def main():
    logger.info("항공권 가격 트래커 시작")

    await init_db()
    await cleanup_past_dates()
    dates = generate_scan_dates()
    logger.info(f"스캔 날짜 {len(dates)}개 생성됨")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        for i, route in enumerate(ROUTES, start=1):
            logger.info(f"구간 스캔 시작: {route['origin']}→{route['destination']} ({route['label']})")
            await scan_route(page, i, route["origin"], route["destination"], dates)
            logger.info(f"구간 스캔 완료: {route['label']}")

        # 구간별 최저가 주 3인 가격 확인
        try:
            await check_pax3_prices(page)
        except Exception as e:
            logger.error(f"3인 가격 체크 실패: {e}")

        await browser.close()

    # 스냅샷 기록 — 실패해도 export는 계속
    try:
        await record_snapshots()
    except Exception as e:
        logger.error(f"스냅샷 기록 실패 (export는 계속 진행): {e}")

    # data.json 내보내기 + GitHub push — 실패해도 스캔 결과는 DB에 보존됨
    try:
        await export_and_push()
    except Exception as e:
        logger.error(f"export_and_push 실패: {e}")

    logger.info("항공권 가격 트래커 완료")


async def record_snapshots():
    """전체 weekly_lowest 기준으로 price_history / weekly_price_history 스냅샷을 기록한다."""
    db = await get_db()
    now_str = datetime.now(KST).isoformat()
    try:
        rows = await db.execute(
            "SELECT route_id, depart_date, return_date, min_price, airline, flight_info "
            "FROM weekly_lowest ORDER BY route_id, min_price"
        )
        rows = await rows.fetchall()

        # 구간별 전체 최저가 (min_price 기준 첫 번째 row)
        seen_routes = set()
        for row in rows:
            rid = row["route_id"]
            if rid not in seen_routes:
                seen_routes.add(rid)
                await insert_price_snapshot(
                    db, rid, now_str,
                    row["min_price"], row["airline"],
                    row["depart_date"], row["flight_info"]
                )
            # 주별 스냅샷
            await insert_weekly_price_snapshot(
                db, rid, row["depart_date"], row["return_date"],
                now_str, row["min_price"], row["airline"], row["flight_info"]
            )
        await db.commit()
        logger.info(f"스냅샷 기록 완료 ({len(rows)}개 주)")
    finally:
        await db.close()


async def export_and_push():
    """DB → data.json 내보내기 후 GitHub에 push한다.

    방어 설계:
    - 메인 쿼리(weekly_lowest) 실패 → 예외 전파 (data.json 미작성)
    - 히스토리 쿼리 실패 → 경고 로그만, 빈 히스토리로 data.json 정상 작성
    - data.json 작성은 DB 연결 종료 후 항상 실행 (finally 외부)
    - git push 실패 → 로그만 (파일은 이미 저장됨)
    """
    import pathlib
    HISTORY_LIMIT = 200

    data = {"updated_at": datetime.now(KST).isoformat(), "routes": []}
    route_map = {}

    db = await get_db()
    try:
        # ── 1. 메인 데이터: weekly_lowest (실패 시 예외 전파)
        route_labels = {r["destination"]: r["label"] for r in ROUTES}
        rows = await db.execute("""
            SELECT r.origin, r.destination,
                   w.depart_date, w.return_date,
                   w.min_price, w.airline, w.flight_info,
                   w.kal_price, w.kal_flight_info,
                   w.pax3_price, w.updated_at
            FROM weekly_lowest w
            JOIN routes r ON w.route_id = r.id
            ORDER BY r.id, w.depart_date
        """)
        async for row in rows:
            key = f"{row['origin']}-{row['destination']}"
            if key not in route_map:
                route_map[key] = {
                    "origin": row["origin"],
                    "destination": row["destination"],
                    "label": route_labels.get(row["destination"], row["destination"]),
                    "weeks": [],
                    "overall_history": [],
                    "weekly_history": {},
                }
            route_map[key]["weeks"].append({
                "depart_date": row["depart_date"],
                "return_date": row["return_date"],
                "min_price": row["min_price"],
                "airline": row["airline"],
                "flight_info": row["flight_info"],
                "kal_price": row["kal_price"],
                "kal_flight_info": row["kal_flight_info"],
                "pax3_price": row["pax3_price"],
                "updated_at": row["updated_at"],
            })
        data["routes"] = list(route_map.values())

        # ── 2. 히스토리 데이터: 실패해도 메인 데이터는 보존
        rid_to_key = {
            i + 1: f"{r['origin']}-{r['destination']}"
            for i, r in enumerate(ROUTES)
        }
        try:
            ph_rows = await db.execute(
                "SELECT route_id, snapshot_at, overall_min_price, airline, depart_date "
                "FROM price_history ORDER BY route_id, snapshot_at DESC"
            )
            ph_by_route: dict = {}
            for row in await ph_rows.fetchall():
                key = rid_to_key.get(row["route_id"])
                if key and key in route_map:
                    ph_by_route.setdefault(key, []).append({
                        "snapshot_at": row["snapshot_at"],
                        "price": row["overall_min_price"],
                        "airline": row["airline"],
                        "depart_date": row["depart_date"],
                    })
            for key, entries in ph_by_route.items():
                route_map[key]["overall_history"] = list(reversed(entries[:HISTORY_LIMIT]))

            wph_rows = await db.execute(
                "SELECT route_id, depart_date, snapshot_at, min_price, airline "
                "FROM weekly_price_history ORDER BY route_id, depart_date, snapshot_at DESC"
            )
            wph_by_key: dict = {}
            for row in await wph_rows.fetchall():
                key = rid_to_key.get(row["route_id"])
                if key and key in route_map:
                    dd = row["depart_date"]
                    wph_by_key.setdefault(key, {}).setdefault(dd, []).append({
                        "snapshot_at": row["snapshot_at"],
                        "price": row["min_price"],
                        "airline": row["airline"],
                    })
            for key, dd_map in wph_by_key.items():
                wh = route_map[key]["weekly_history"]
                for dd, entries in dd_map.items():
                    wh[dd] = list(reversed(entries[:HISTORY_LIMIT]))

        except Exception as e:
            logger.warning(f"히스토리 쿼리 실패 (빈 히스토리로 진행): {e}")

    finally:
        await db.close()

    repo_dir = pathlib.Path(__file__).parent
    data_path = repo_dir / "data.json"
    with open(data_path, "w", encoding="utf-8") as f:
        _json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"data.json 저장 완료 ({len(data['routes'])}개 구간)")

    try:
        subprocess.run(["git", "-C", str(repo_dir), "add", "data.json"], check=True)
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "diff", "--cached", "--quiet"],
            capture_output=True
        )
        if result.returncode != 0:  # 변경사항 있을 때만 커밋
            now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
            subprocess.run(
                ["git", "-C", str(repo_dir), "commit", "-m", f"data: {now_str} 가격 업데이트"],
                check=True
            )
            subprocess.run(["git", "-C", str(repo_dir), "push"], check=True)
            logger.info("GitHub push 완료")
        else:
            logger.info("변경사항 없음, push 생략")
    except subprocess.CalledProcessError as e:
        logger.error(f"GitHub push 실패: {e}")


if __name__ == "__main__":
    asyncio.run(main())
