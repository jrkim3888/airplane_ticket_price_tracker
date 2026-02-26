"use client";

import { useState } from "react";
import { Route } from "@/lib/types";
import {
  formatPrice,
  formatDate,
  parseFlightTimes,
  getNaverLink,
  calcNights,
} from "@/lib/utils";

type SortKey = "depart_date" | "min_price" | "kal_price";
type SortDir = "asc" | "desc";

export default function WeeklyTable({ route }: { route: Route }) {
  const today = new Date().toISOString().split("T")[0];
  const [sortKey, setSortKey] = useState<SortKey>("depart_date");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const future = route.weeks.filter((w) => w.depart_date >= today);

  const sorted = [...future].sort((a, b) => {
    let av: number, bv: number;
    if (sortKey === "depart_date") {
      av = new Date(a.depart_date).getTime();
      bv = new Date(b.depart_date).getTime();
    } else if (sortKey === "min_price") {
      av = a.min_price;
      bv = b.min_price;
    } else {
      // kal_price: null을 맨 뒤로
      av = a.kal_price ?? Infinity;
      bv = b.kal_price ?? Infinity;
    }
    return sortDir === "asc" ? av - bv : bv - av;
  });

  const lowestPrice = [...future].sort((a, b) => a.min_price - b.min_price)[0]
    ?.min_price;

  const SortBtn = ({ col, label }: { col: SortKey; label: string }) => {
    const active = sortKey === col;
    return (
      <button
        onClick={() => handleSort(col)}
        className={`flex items-center gap-0.5 group ${
          active ? "text-blue-600" : "text-gray-600 hover:text-gray-900"
        }`}
      >
        {label}
        <span className="text-xs ml-0.5">
          {active ? (sortDir === "asc" ? "↑" : "↓") : <span className="text-gray-300 group-hover:text-gray-400">↕</span>}
        </span>
      </button>
    );
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-4 sm:p-6 pb-2">
        <h3 className="text-base sm:text-lg font-semibold text-gray-800">
          📋 주별 최저가
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-gray-600">
              <th className="px-3 py-2 text-left font-medium">
                <SortBtn col="depart_date" label="출발일" />
              </th>
              <th className="px-3 py-2 text-left font-medium">귀국일</th>
              <th className="px-3 py-2 text-center font-medium">박수</th>
              <th className="px-3 py-2 text-right font-medium">
                <SortBtn col="min_price" label="최저가" />
              </th>
              <th className="px-3 py-2 text-left font-medium">항공사</th>
              <th className="px-3 py-2 text-left font-medium hidden sm:table-cell">
                가는편
              </th>
              <th className="px-3 py-2 text-left font-medium hidden sm:table-cell">
                오는편
              </th>
              <th className="px-3 py-2 text-right font-medium">
                <SortBtn col="kal_price" label="KAL" />
              </th>
              <th className="px-3 py-2 text-center font-medium">링크</th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-gray-400">
                  예정된 항공편 없음
                </td>
              </tr>
            )}
            {sorted.map((week) => {
              const flights = parseFlightTimes(week.flight_info);
              const isLowest = week.min_price === lowestPrice;
              const nights = calcNights(week.depart_date, week.return_date);
              return (
                <tr
                  key={`${week.depart_date}-${week.return_date}`}
                  className={
                    isLowest
                      ? "bg-amber-50 border-l-4 border-amber-400"
                      : "hover:bg-gray-50 border-l-4 border-transparent"
                  }
                >
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {formatDate(week.depart_date)}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {formatDate(week.return_date)}
                  </td>
                  <td className="px-3 py-2.5 text-center whitespace-nowrap">
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                      nights === 2
                        ? "bg-blue-100 text-blue-700"
                        : "bg-purple-100 text-purple-700"
                    }`}>
                      {nights}박
                    </span>
                  </td>
                  <td
                    className={`px-3 py-2.5 text-right font-semibold whitespace-nowrap ${
                      isLowest ? "text-amber-700" : "text-gray-800"
                    }`}
                  >
                    {formatPrice(week.min_price)}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap">
                    {week.airline}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap hidden sm:table-cell text-gray-600">
                    {flights.outbound}
                  </td>
                  <td className="px-3 py-2.5 whitespace-nowrap hidden sm:table-cell text-gray-600">
                    {flights.inbound}
                  </td>
                  <td className="px-3 py-2.5 text-right whitespace-nowrap text-gray-600">
                    {formatPrice(week.kal_price)}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <a
                      href={getNaverLink(
                        route.origin,
                        route.destination,
                        week.depart_date,
                        week.return_date
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-green-600 hover:text-green-800 text-xs font-medium"
                    >
                      검색↗
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
