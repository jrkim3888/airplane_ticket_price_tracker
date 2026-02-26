import { FlightData } from "./types";

const DATA_URL =
  "https://raw.githubusercontent.com/jrkim3888/airplane_ticket_price_tracker/main/data.json";

export async function fetchFlightData(): Promise<FlightData> {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch flight data");
  return res.json();
}
