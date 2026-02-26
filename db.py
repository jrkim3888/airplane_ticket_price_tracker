"""항공권 가격 트래커 - SQLite 헬퍼"""

import aiosqlite
from config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY,
    origin TEXT,
    destination TEXT,
    depart_time_from INTEGER DEFAULT 18,
    return_time_from INTEGER DEFAULT 16
);

CREATE TABLE IF NOT EXISTS weekly_lowest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    depart_date TEXT,
    return_date TEXT,
    min_price INTEGER,
    airline TEXT,
    flight_info TEXT,
    kal_price INTEGER,
    kal_flight_info TEXT,
    pax3_price INTEGER,
    updated_at TEXT,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    depart_date TEXT,
    return_date TEXT,
    price INTEGER,
    airline TEXT,
    flight_info TEXT,
    scanned_at TEXT,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_weekly_lowest_route_dates
    ON weekly_lowest(route_id, depart_date, return_date);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    snapshot_at TEXT,
    overall_min_price INTEGER,
    airline TEXT,
    depart_date TEXT,
    flight_info TEXT,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

CREATE TABLE IF NOT EXISTS weekly_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id INTEGER,
    depart_date TEXT,
    return_date TEXT,
    snapshot_at TEXT,
    min_price INTEGER,
    airline TEXT,
    flight_info TEXT,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);
"""


async def get_db() -> aiosqlite.Connection:
    """DB 커넥션을 반환한다."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db():
    """스키마를 생성하고 routes 테이블을 초기화한다."""
    from config import ROUTES, DEPART_TIME_FROM, RETURN_TIME_FROM

    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)

        # 마이그레이션: pax3_price 컬럼 추가 (기존 DB 대응)
        cols = await db.execute("PRAGMA table_info(weekly_lowest)")
        col_names = [row["name"] for row in await cols.fetchall()]
        if "pax3_price" not in col_names:
            await db.execute(
                "ALTER TABLE weekly_lowest ADD COLUMN pax3_price INTEGER"
            )
            await db.commit()

        for i, route in enumerate(ROUTES, start=1):
            existing = await db.execute(
                "SELECT id FROM routes WHERE id = ?", (i,)
            )
            if await existing.fetchone() is None:
                await db.execute(
                    "INSERT INTO routes (id, origin, destination, depart_time_from, return_time_from) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (i, route["origin"], route["destination"], DEPART_TIME_FROM, RETURN_TIME_FROM),
                )
        await db.commit()
    finally:
        await db.close()


async def is_duplicate_scan(db, route_id: int, depart_date: str, return_date: str,
                            price: int, scanned_at_minute: str) -> bool:
    """동일 route_id + depart_date + return_date + price가 같은 분에 이미 존재하는지 확인."""
    cursor = await db.execute(
        "SELECT 1 FROM scan_history WHERE route_id = ? AND depart_date = ? "
        "AND return_date = ? AND price = ? AND substr(scanned_at, 1, 16) = ?",
        (route_id, depart_date, return_date, price, scanned_at_minute),
    )
    return await cursor.fetchone() is not None


async def insert_scan(db, route_id: int, depart_date: str, return_date: str,
                      price: int, airline: str, flight_info: str, scanned_at: str):
    """scan_history에 기록을 추가한다."""
    scanned_at_minute = scanned_at[:16]
    if await is_duplicate_scan(db, route_id, depart_date, return_date, price, scanned_at_minute):
        return

    await db.execute(
        "INSERT INTO scan_history (route_id, depart_date, return_date, price, airline, flight_info, scanned_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (route_id, depart_date, return_date, price, airline, flight_info, scanned_at),
    )


async def update_weekly_lowest(db, route_id: int, depart_date: str, return_date: str,
                               price: int, airline: str, flight_info: str,
                               kal_price, kal_flight_info, updated_at: str):
    """weekly_lowest를 갱신한다. 최저가가 갱신되었으면 (old_price, new_price)를, 아니면 None을 반환."""
    cursor = await db.execute(
        "SELECT min_price FROM weekly_lowest WHERE route_id = ? AND depart_date = ? AND return_date = ?",
        (route_id, depart_date, return_date),
    )
    row = await cursor.fetchone()

    if row is None:
        # 신규 삽입
        await db.execute(
            "INSERT INTO weekly_lowest (route_id, depart_date, return_date, min_price, airline, "
            "flight_info, kal_price, kal_flight_info, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (route_id, depart_date, return_date, price, airline, flight_info,
             kal_price, kal_flight_info, updated_at),
        )
        return (None, price)

    old_price = row[0] if isinstance(row, tuple) else row["min_price"]

    if price < old_price:
        await db.execute(
            "UPDATE weekly_lowest SET min_price = ?, airline = ?, flight_info = ?, "
            "kal_price = ?, kal_flight_info = ?, updated_at = ? "
            "WHERE route_id = ? AND depart_date = ? AND return_date = ?",
            (price, airline, flight_info, kal_price, kal_flight_info, updated_at,
             route_id, depart_date, return_date),
        )
        return (old_price, price)

    # 최저가 아니더라도 대한항공 정보 업데이트
    if kal_price is not None:
        await db.execute(
            "UPDATE weekly_lowest SET kal_price = ?, kal_flight_info = ?, updated_at = ? "
            "WHERE route_id = ? AND depart_date = ? AND return_date = ?",
            (kal_price, kal_flight_info, updated_at, route_id, depart_date, return_date),
        )

    return None


async def get_all_weekly_lowest(db):
    """전체 weekly_lowest를 route별, 날짜순으로 반환."""
    cursor = await db.execute(
        "SELECT wl.*, r.origin, r.destination "
        "FROM weekly_lowest wl "
        "JOIN routes r ON wl.route_id = r.id "
        "ORDER BY wl.route_id, wl.depart_date"
    )
    return await cursor.fetchall()


async def get_routes(db):
    """전체 routes를 반환."""
    cursor = await db.execute("SELECT * FROM routes ORDER BY id")
    return await cursor.fetchall()


async def insert_price_snapshot(db, route_id: int, snapshot_at: str,
                                 overall_min_price: int, airline: str,
                                 depart_date: str, flight_info: str):
    """구간 전체 최저가 스냅샷을 price_history에 기록한다."""
    await db.execute(
        "INSERT INTO price_history (route_id, snapshot_at, overall_min_price, airline, depart_date, flight_info) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (route_id, snapshot_at, overall_min_price, airline, depart_date, flight_info),
    )


async def insert_weekly_price_snapshot(db, route_id: int, depart_date: str,
                                        return_date: str, snapshot_at: str,
                                        min_price: int, airline: str, flight_info: str):
    """주별 최저가 스냅샷을 weekly_price_history에 기록한다. 중복 방지(같은 시간+같은 가격)."""
    existing = await db.execute(
        "SELECT 1 FROM weekly_price_history "
        "WHERE route_id=? AND depart_date=? AND substr(snapshot_at,1,13)=substr(?,1,13) AND min_price=?",
        (route_id, depart_date, snapshot_at, min_price)
    )
    if await existing.fetchone():
        return
    await db.execute(
        "INSERT INTO weekly_price_history (route_id, depart_date, return_date, snapshot_at, min_price, airline, flight_info) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (route_id, depart_date, return_date, snapshot_at, min_price, airline, flight_info),
    )
