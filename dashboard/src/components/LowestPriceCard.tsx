import { Route, WeekEntry } from "@/lib/types";
import {
  formatPrice,
  formatDate,
  parseFlightTimes,
  getNaverLink,
  getOriginName,
  calcNights,
} from "@/lib/utils";

export default function LowestPriceCard({ route }: { route: Route }) {
  const today = new Date().toISOString().split("T")[0];
  const futureWeeks = route.weeks.filter(
    (w) => w.min_price > 0 && w.depart_date >= today
  );
  const sorted = [...futureWeeks].sort((a, b) => a.min_price - b.min_price);

  const best: WeekEntry | undefined = sorted[0];

  // 최저가 출발일과 같은 날 다른 박수 옵션 (2박↔3박 비교)
  const bestNights = best ? calcNights(best.depart_date, best.return_date) : 0;
  const altOption = best
    ? futureWeeks.find(
        (w) =>
          w.depart_date === best.depart_date &&
          w.return_date !== best.return_date
      )
    : null;
  const altNights = altOption
    ? calcNights(altOption.depart_date, altOption.return_date)
    : 0;

  const kalWeeks = route.weeks.filter(
    (w) => w.kal_price !== null && w.depart_date >= today
  );
  const bestKal = kalWeeks.length
    ? kalWeeks.sort((a, b) => a.kal_price! - b.kal_price!)[0]
    : null;

  const bestFlights = best ? parseFlightTimes(best.flight_info) : null;
  const kalFlights =
    bestKal?.kal_flight_info
      ? parseFlightTimes(bestKal.kal_flight_info)
      : null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 sm:p-6">
      <h2 className="text-lg sm:text-xl font-bold text-gray-800 mb-4">
        {getOriginName(route.origin)} → {route.label}
      </h2>

      {best ? (
        <div className="space-y-4">
          {/* 전체 최저가 */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 sm:p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">🏆</span>
              <span className="font-semibold text-amber-800">전체 최저가</span>
            </div>
            <div className="text-2xl sm:text-3xl font-bold text-amber-700 mb-1">
              {formatPrice(best.min_price)}
            </div>
            <div className="text-sm text-gray-600 space-y-1">
              <div>
                📅 {formatDate(best.depart_date)} ~{" "}
                {formatDate(best.return_date)}{" "}
                <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                  {bestNights}박
                </span>
              </div>
              <div>🛫 {best.airline}</div>
              {bestFlights && (
                <>
                  <div>가는편: {bestFlights.outbound}</div>
                  <div>오는편: {bestFlights.inbound}</div>
                </>
              )}
            </div>
            {altOption && (
              <div className="mt-3 pt-3 border-t border-amber-200">
                <div className="text-xs text-amber-700 font-medium mb-1">
                  같은 출발일 {altNights}박 옵션
                </div>
                <div className="flex items-center justify-between">
                  <div className="text-sm text-gray-600">
                    <span className="font-semibold text-gray-800">
                      {formatPrice(altOption.min_price)}
                    </span>
                    {" · "}{altOption.airline}
                  </div>
                  <a
                    href={getNaverLink(
                      route.origin,
                      route.destination,
                      altOption.depart_date,
                      altOption.return_date
                    )}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-green-600 hover:text-green-800"
                  >
                    검색↗
                  </a>
                </div>
              </div>
            )}
            <a
              href={getNaverLink(
                route.origin,
                route.destination,
                best.depart_date,
                best.return_date
              )}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-3 px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors"
            >
              네이버에서 검색
            </a>
          </div>

          {/* 대한항공 */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">🇰🇷</span>
              <span className="font-semibold text-blue-800">대한항공</span>
            </div>
            {bestKal && bestKal.kal_price !== null ? (
              <>
                <div className="text-xl sm:text-2xl font-bold text-blue-700 mb-1">
                  {formatPrice(bestKal.kal_price)}
                </div>
                <div className="text-sm text-gray-600 space-y-1">
                  <div>
                    📅 {formatDate(bestKal.depart_date)} ~{" "}
                    {formatDate(bestKal.return_date)}
                  </div>
                  {kalFlights && (
                    <>
                      <div>가는편: {kalFlights.outbound}</div>
                      <div>오는편: {kalFlights.inbound}</div>
                    </>
                  )}
                </div>
                <a
                  href={getNaverLink(
                    route.origin,
                    route.destination,
                    bestKal.depart_date,
                    bestKal.return_date
                  )}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block mt-3 px-4 py-2 bg-green-500 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  네이버에서 검색
                </a>
              </>
            ) : (
              <div className="text-gray-500">없음</div>
            )}
          </div>
        </div>
      ) : (
        <div className="text-gray-500">가격 정보 없음</div>
      )}
    </div>
  );
}
