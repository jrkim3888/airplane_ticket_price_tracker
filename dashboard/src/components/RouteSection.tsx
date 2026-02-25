import { Route } from "@/lib/types";
import LowestPriceCard from "./LowestPriceCard";
import WeeklyTable from "./WeeklyTable";
import OverallChart from "./OverallChart";
import WeeklyChart from "./WeeklyChart";

export default function RouteSection({ route }: { route: Route }) {
  return (
    <section className="space-y-4">
      <LowestPriceCard route={route} />
      <WeeklyTable route={route} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OverallChart history={route.overall_history} />
        <WeeklyChart weeklyHistory={route.weekly_history} />
      </div>
    </section>
  );
}
