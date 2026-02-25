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
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hour = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${month}/${day} ${hour}:${min}`;
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
