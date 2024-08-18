import { ArrowRight, Footprints, TrainFront } from 'lucide-react';
import { CityData, Route } from '../types';

interface RouteGuideProps {
  route: Route;
  cityData: CityData;
}

function getLineName(cityData: CityData, lineId: string): string {
  return cityData.lines.find(line => line.id === lineId)?.name || lineId;
}

export function RouteGuide({ route, cityData }: RouteGuideProps) {
  const start = route.stations[0];
  const end = route.stations[route.stations.length - 1];
  const lineNames = route.lines.map(lineId => getLineName(cityData, lineId));

  return (
    <div className="rounded-[28px] border border-white/80 bg-white/90 p-4 shadow-lg shadow-slate-200/70">
      <div className="mb-3 flex items-center gap-2 text-base font-black text-slate-700">
        <Footprints className="h-5 w-5 text-teal-600" />
        跟着小列车走一遍
      </div>
      <div className="grid gap-3">
        <div className="flex items-center gap-3 rounded-2xl bg-emerald-50 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white">1</div>
          <div className="font-bold text-slate-700">从 <span className="text-slate-900">{start.name}</span> 出发</div>
        </div>
        <div className="flex items-center gap-3 rounded-2xl bg-sky-50 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 text-white">2</div>
          <div className="flex min-w-0 flex-wrap items-center gap-2 font-bold text-slate-700">
            {lineNames.map((lineName, index) => (
              <span key={`${lineName}-${index}`} className="inline-flex items-center gap-2">
                <TrainFront className="h-4 w-4 text-sky-600" />
                {lineName}
                {index < lineNames.length - 1 && <ArrowRight className="h-4 w-4 text-slate-400" />}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-2xl bg-rose-50 p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-rose-500 text-white">3</div>
          <div className="font-bold text-slate-700">到 <span className="text-slate-900">{end.name}</span> 下车</div>
        </div>
      </div>
    </div>
  );
}
