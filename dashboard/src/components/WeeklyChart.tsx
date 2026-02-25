"use client";

import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { WeeklyHistoryEntry } from "@/lib/types";
import { formatPrice, formatDate } from "@/lib/utils";

function formatChartDate(isoStr: string): string {
  const d = new Date(isoStr);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function WeeklyChart({
  weeklyHistory,
}: {
  weeklyHistory: Record<string, WeeklyHistoryEntry[]>;
}) {
  const weeks = Object.keys(weeklyHistory).sort();
  const [selected, setSelected] = useState(weeks[0] || "");

  if (weeks.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold text-gray-800 mb-4">
          📊 주별 가격 추이
        </h3>
        <div className="text-gray-500 text-sm">히스토리 데이터 없음</div>
      </div>
    );
  }

  const entries = weeklyHistory[selected] || [];
  const data = entries.map((e) => ({
    time: formatChartDate(e.snapshot_at),
    price: e.price,
    airline: e.airline,
  }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 sm:p-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <h3 className="text-base sm:text-lg font-semibold text-gray-800">
          📊 주별 가격 추이
        </h3>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {weeks.map((w) => (
            <option key={w} value={w}>
              출발 {formatDate(w)}
            </option>
          ))}
        </select>
      </div>
      {data.length > 0 ? (
        <div className="h-64 sm:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11 }}
                angle={-30}
                textAnchor="end"
                height={50}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
                width={45}
              />
              <Tooltip
                formatter={(value: number) => [formatPrice(value), "가격"]}
                labelStyle={{ fontSize: 12 }}
              />
              <Line
                type="monotone"
                dataKey="price"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="text-gray-500 text-sm">
          선택한 주차의 히스토리 데이터 없음
        </div>
      )}
    </div>
  );
}
