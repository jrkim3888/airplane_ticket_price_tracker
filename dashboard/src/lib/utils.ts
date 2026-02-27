const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00+09:00");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const dayName = DAY_NAMES[d.getDay()];
  return `${month}/${day}(${dayName})`;
}

export function formatPrice(price: number | null): string {
  if (price === null || price === undefined) return "없음";
  return price.toLocaleString("ko-KR") + "원";
}

export function formatDateTime(isoStr: string): string {
  const d = new Date(isoStr);
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (type: string) =>
    parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("month")}/${get("day")} ${get("hour")}:${get("minute")} KST`;
}

export function getNaverLink(
  origin: string,
  destination: string,
  departDate: string,
  returnDate: string
): string {
  const dep = departDate.replace(/-/g, "");
  const ret = returnDate.replace(/-/g, "");
  return `https://flight.naver.com/flights/international/${origin}-${destination}-${dep}/${destination}-${origin}-${ret}?adult=1&fareType=Y`;
}

export function parseFlightTimes(info: string): {
  outbound: string;
  inbound: string;
} {
  const parts = info.split(" / ");
  return {
    outbound: parts[0]?.trim() || "-",
    inbound: parts[1]?.trim() || "-",
  };
}

const ORIGIN_NAMES: Record<string, string> = {
  ICN: "인천",
  GMP: "김포",
};

export function getOriginName(code: string): string {
  return ORIGIN_NAMES[code] || code;
}

// 국기 이모지(Regional Indicator 2자) → flagcdn.com URL
// 예: "🇯🇵 후쿠오카" → "https://flagcdn.com/24x18/jp.png"
export function getFlagUrl(label: string): string | null {
  const codePoints = Array.from(label).map((c) => c.codePointAt(0) ?? 0);
  const indicators: number[] = [];
  for (const cp of codePoints) {
    if (cp >= 0x1f1e6 && cp <= 0x1f1ff) {
      indicators.push(cp - 0x1f1e6); // 0=A … 25=Z
    }
  }
  if (indicators.length < 2) return null;
  const code = String.fromCharCode(65 + indicators[0], 65 + indicators[1]).toLowerCase();
  return `https://flagcdn.com/24x18/${code}.png`;
}

// 국기 이모지 + 공백 접두사 제거 → 순수 도시명
// 예: "🇯🇵 후쿠오카" → "후쿠오카"
export function getLabelText(label: string): string {
  return label
    .replace(/^[\uD83C][\uDDE6-\uDDFF][\uD83C][\uDDE6-\uDDFF]\s*/, "")
    .trim();
}

export function calcNights(departDate: string, returnDate: string): number {
  const d = new Date(departDate + "T00:00:00+09:00");
  const r = new Date(returnDate + "T00:00:00+09:00");
  return Math.round((r.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
}
