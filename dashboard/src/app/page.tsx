import { fetchFlightData } from "@/lib/data";
import { formatDateTime } from "@/lib/utils";
import RouteSection from "@/components/RouteSection";

export default async function Home() {
  const data = await fetchFlightData();

  return (
    <main className="max-w-5xl mx-auto px-4 py-6 sm:py-8">
      {/* 헤더 */}
      <header className="mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
          ✈️ 항공권 가격 트래커
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          마지막 업데이트: {formatDateTime(data.updated_at)}
        </p>
      </header>

      {/* 구간별 섹션 */}
      <div className="space-y-10">
        {data.routes.map((route) => (
          <RouteSection
            key={`${route.origin}-${route.destination}`}
            route={route}
          />
        ))}
      </div>
    </main>
  );
}
