"""항공권 가격 트래커 - 브리핑 발송 (가격 재검증 포함)"""

import asyncio
import logging
import urllib.request
import urllib.error
import json
import ssl
import subprocess as _sp
from datetime import datetime
from collections import defaultdict

import pytz
from playwright.async_api import async_playwright

from config import ALL_ROUTES as ROUTES, DISCORD_CHANNEL_ID, BRIEFING_HOURS_KST, DEPART_TIME_FROM, RETURN_TIME_FROM
from db import init_db, get_db, get_all_weekly_lowest, update_weekly_lowest
from tracker import scrape_flights, parse_naver_flights

# Discord 봇 토큰
_token_result = _sp.run(
    ["openclaw", "config", "get", "channels.discord.token"],
    capture_output=True, text=True
)
DISCORD_BOT_TOKEN = _token_result.stdout.strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

KST = pytz.timezone("Asia/Seoul")
WEEKDAYS_KR = ["월", "화", "수", "목", "금", "토", "일"]


# ── Discord 전송 ──────────────────────────────────────────

def send_discord(message: str):
    url = f"https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages"
    payload = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "mc-mini-flight-tracker/1.0",
        },
        method="POST",
    )
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
            if resp.status in (200, 201):
                logger.info("Discord 브리핑 전송 완료")
            else:
                logger.error(f"Discord 전송 실패: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        logger.error(f"Discord 전송 실패: HTTP {e.code} {e.read().decode()}")
    except Exception as e:
        logger.error(f"Discord 전송 실패: {e}")


# ── 포맷 헬퍼 ────────────────────────────────────────────

def get_next_briefing_hour(now_hour: int) -> str:
    for h in BRIEFING_HOURS_KST:
        if h > now_hour:
            return f"{h:02d}:00 KST"
    return f"{BRIEFING_HOURS_KST[0]:02d}:00 KST"


def format_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.month:02d}/{dt.day:02d}({WEEKDAYS_KR[dt.weekday()]})"


def format_schedule(flight_info: str) -> tuple[str, str]:
    try:
        out_part, ret_part = flight_info.split(" / ")
        return out_part.strip(), ret_part.strip()
    except ValueError:
        return flight_info, ""


def naver_url(origin: str, destination: str, depart_date: str, return_date: str) -> str:
    d = depart_date.replace("-", "")
    r = return_date.replace("-", "")
    return (
        f"<https://flight.naver.com/flights/international/"
        f"{origin}-{destination}-{d}/{destination}-{origin}-{r}?adult=1&fareType=Y>"
    )


# ── 가격 재검증 ───────────────────────────────────────────

async def verify_route_best(page, route: dict, route_rows: list, route_id: int, db) -> tuple:
    """
    해당 구간의 현재 최저가 주를 Naver에서 재검증한다.

    Returns:
        (best_row_or_None, warning_str_or_None)
    """
    if not route_rows:
        return None, None

    best = min(route_rows, key=lambda r: r["min_price"])
    origin = route["origin"]
    destination = route["destination"]
    depart_date = best["depart_date"]
    return_date = best["return_date"]
    old_price = best["min_price"]

    depart_d = depart_date.replace("-", "")
    return_d = return_date.replace("-", "")
    url = (
        f"https://flight.naver.com/flights/international/"
        f"{origin}-{destination}-{depart_d}/{destination}-{origin}-{return_d}"
        f"?adult=1&fareType=Y"
    )

    logger.info(f"[검증] {origin}→{destination} {depart_date} 재확인 중...")
    result = await scrape_flights(page, url, origin, destination, DEPART_TIME_FROM, RETURN_TIME_FROM)

    now_str = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S")

    if result is None:
        # 결과 없음 → 일시적 오류일 수 있으므로 DB 건드리지 않음
        # 삭제는 크롤러(tracker.py)가 담당
        logger.warning(f"[검증] {origin}→{destination} {depart_date} 실시간 확인 불가 (일시 오류 가능)")
        warning = f"⚠️ {format_date(depart_date)} 출발 실시간 확인 불가 — DB 기준 가격 표시"
        return best, warning

    new_price = result["min_price"]

    if new_price < old_price:
        # 가격 더 내려감 → 업데이트
        logger.info(f"[검증] {origin}→{destination} {depart_date} 가격 인하: {old_price:,} → {new_price:,}")
        await update_weekly_lowest(
            db, route_id, depart_date, return_date,
            result["min_price"], result["airline"], result["flight_info"],
            result["kal_price"], result["kal_flight_info"], now_str
        )
        await db.commit()
        best = dict(best)
        best.update({
            "min_price": result["min_price"], "airline": result["airline"],
            "flight_info": result["flight_info"], "kal_price": result["kal_price"],
            "kal_flight_info": result["kal_flight_info"],
        })
        warning = f"✨ 가격 인하! {old_price:,}원 → {new_price:,}원"
        return best, warning

    elif new_price > old_price:
        # 가격 올라감 (이전 최저가 소멸) → DB 업데이트
        logger.info(f"[검증] {origin}→{destination} {depart_date} 이전 최저가 소멸: {old_price:,} → {new_price:,}")
        await update_weekly_lowest(
            db, route_id, depart_date, return_date,
            result["min_price"], result["airline"], result["flight_info"],
            result["kal_price"], result["kal_flight_info"], now_str
        )
        await db.commit()
        best = dict(best)
        best.update({
            "min_price": result["min_price"], "airline": result["airline"],
            "flight_info": result["flight_info"], "kal_price": result["kal_price"],
            "kal_flight_info": result["kal_flight_info"],
        })
        warning = f"⚠️ 이전 최저가 소멸 ({old_price:,}원) → 현재: {new_price:,}원"
        return best, warning

    else:
        # 가격 동일 → 유효 확인
        logger.info(f"[검증] {origin}→{destination} {depart_date} 가격 유효 확인 ({new_price:,}원)")
        return best, None


# ── 브리핑 메시지 생성 ────────────────────────────────────

def build_briefing_message(verified_data: list) -> str:
    """
    verified_data: [
        {
            "route": dict,
            "best": row_or_None,
            "warning": str_or_None,
        },
        ...
    ]
    """
    now = datetime.now(KST)
    now_str = now.strftime("%Y-%m-%d %H:%M")

    lines = [f"✈️ 항공권 가격 브리핑 | {now_str} KST"]
    lines.append("")

    for item in verified_data:
        route = item["route"]
        best = item["best"]
        warning = item["warning"]
        label = route["label"]
        origin = route["origin"]
        destination = route["destination"]

        lines.append(f"📍 인천 → {label} (직항)")
        lines.append("━━━━━━━━━━━━━━━━━━━━")

        # 경고 메시지 (가격 변동/소멸)
        if warning:
            lines.append(warning)

        if best is None:
            lines.append("   데이터 없음 (스캔 대기 중)")
            lines.append("")
            continue

        depart_date = best["depart_date"]
        return_date = best["return_date"]
        min_price = best["min_price"]
        airline = best["airline"]
        flight_info = best["flight_info"]
        kal_price = best["kal_price"]
        kal_flight_info = best["kal_flight_info"]

        dd_str = format_date(depart_date)
        rd_str = format_date(return_date)
        out_leg, ret_leg = format_schedule(flight_info)
        search_url = naver_url(origin, destination, depart_date, return_date)

        lines.append(f"🏆 최저가: {dd_str} → {rd_str} | {airline}")
        lines.append(f"   ↗ 가는편: {out_leg}")
        lines.append(f"   ↙ 오는편: {ret_leg}")
        lines.append(f"   💰 왕복 {min_price:,}원")
        lines.append(f"   🔗 {search_url}")
        lines.append("")

        if kal_price is not None and kal_flight_info is not None:
            kal_out, kal_ret = format_schedule(kal_flight_info)
            lines.append(f"🇰🇷 대한항공: {dd_str} → {rd_str}")
            lines.append(f"   ↗ 가는편: {kal_out}")
            lines.append(f"   ↙ 오는편: {kal_ret}")
            lines.append(f"   💰 왕복 {kal_price:,}원")
        else:
            lines.append("🇰🇷 대한항공: 해당 시간대 KAL 없음")

        lines.append("")

    next_briefing = get_next_briefing_hour(now.hour)
    lines.append(f"📊 다음 브리핑: {next_briefing}")

    return "\n".join(lines)


# ── 메인 ─────────────────────────────────────────────────

async def main():
    logger.info("브리핑 발송 시작 (가격 재검증 포함)")

    await init_db()
    db = await get_db()

    try:
        rows = await get_all_weekly_lowest(db)

        # route별로 그룹화
        route_data = defaultdict(list)
        for row in rows:
            route_data[row["route_id"]].append(row)

        verified_data = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="ko-KR",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

            for route_id, route in enumerate(ROUTES, start=1):
                route_rows = route_data.get(route_id, [])
                best, warning = await verify_route_best(page, route, route_rows, route_id, db)
                verified_data.append({"route": route, "best": best, "warning": warning})

            await browser.close()

        message = build_briefing_message(verified_data)
        logger.info(f"브리핑 메시지:\n{message}")
        send_discord(message)

    finally:
        await db.close()

    logger.info("브리핑 발송 완료")


if __name__ == "__main__":
    asyncio.run(main())
