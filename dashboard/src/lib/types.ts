export interface WeekEntry {
  depart_date: string;
  return_date: string;
  min_price: number;
  airline: string;
  flight_info: string;
  kal_price: number | null;
  kal_flight_info: string | null;
  updated_at: string;
}

export interface HistoryEntry {
  snapshot_at: string;
  price: number;
  airline: string;
  depart_date: string;
}

export interface WeeklyHistoryEntry {
  snapshot_at: string;
  price: number;
  airline: string;
}

export interface Route {
  origin: string;
  destination: string;
  label: string;
  weeks: WeekEntry[];
  overall_history: HistoryEntry[];
  weekly_history: Record<string, WeeklyHistoryEntry[]>;
}

export interface FlightData {
  updated_at: string;
  routes: Route[];
}
