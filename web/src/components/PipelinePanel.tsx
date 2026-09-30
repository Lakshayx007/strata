import { AlertTriangle } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';
import { CHART_COLORS } from '../utils';

interface PipelinePanelProps {
  data: {
    win_rate_by_competitor: Array<{
      competitor: string;
      total: number;
      wins: number;
      win_rate: number;
    }>;
    stage_conversion: Array<{
      stage: string;
      entries: number;
      median_days: number;
    }>;
    churn_by_usage_decile: Array<{
      usage_decile: number;
      accounts: number;
      churned: number;
      churn_rate: number;
    }>;
    delivery_velocity: Array<{
      pm_team: string;
      total_sprints: number;
      avg_delivered: number;
      on_time_pct: number;
      avg_slip_days: number;
    }>;
  };
}

export default function PipelinePanel({ data }: PipelinePanelProps) {
  return (
    <div className="space-y-8">
      {/* SIMULATED banner */}
      <div className="flex items-center gap-2 p-3 border-2 border-amber-400 dark:border-amber-600 rounded-lg bg-amber-50 dark:bg-amber-950/20">
        <AlertTriangle size={20} className="text-amber-600 shrink-0" />
        <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
          SIMULATED DATA — generated from parameters calibrated to phase-1
          stated-reason shares. Not real CRM data.
        </p>
      </div>

      {/* Win rate by competitor */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Win rate by competitor</h3>
        <div className="h-72" role="img" aria-label="Bar chart of win rate by competitor">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data.win_rate_by_competitor}
              layout="vertical"
              margin={{ top: 5, right: 80, left: 10, bottom: 5 }}
            >
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="competitor"
                width={100}
                tick={{ fontSize: 12, fill: 'currentColor' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg text-sm">
                      <p className="font-semibold">{d.competitor}</p>
                      <p>Wins: {d.wins} / {d.total}</p>
                      <p>Win rate: {(d.win_rate * 100).toFixed(1)}%</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="win_rate" fill={CHART_COLORS[0]} radius={[0, 4, 4, 0]} maxBarSize={28}>
                <LabelList
                  dataKey="win_rate"
                  position="right"
                  formatter={(v: any) => `${(Number(v) * 100).toFixed(1)}%`}
                  style={{ fontSize: 12, fill: 'currentColor' }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Stage bottlenecks */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Stage bottlenecks</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 pr-4 font-semibold">Stage</th>
                <th className="py-2 pr-4 font-semibold text-right">Entries</th>
                <th className="py-2 font-semibold text-right">Avg days</th>
              </tr>
            </thead>
            <tbody>
              {data.stage_conversion.map((s) => (
                <tr
                  key={s.stage}
                  className="border-b border-gray-100 dark:border-gray-800"
                >
                  <td className="py-2 pr-4">{s.stage}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {s.entries}
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {s.median_days}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Churn by decile */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Churn by usage decile</h3>
        <div className="h-56" role="img" aria-label="Bar chart of churn rate by usage decile">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data.churn_by_usage_decile}
              margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
            >
              <XAxis
                dataKey="usage_decile"
                tick={{ fontSize: 11, fill: 'currentColor' }}
                label={{ value: 'Usage decile', position: 'insideBottom', offset: -5, fontSize: 11 }}
              />
              <YAxis hide />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg text-sm">
                      <p>Decile {d.usage_decile}</p>
                      <p>Churned: {d.churned} / {d.accounts}</p>
                      <p>Rate: {(d.churn_rate * 100).toFixed(1)}%</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="churn_rate" fill={CHART_COLORS[4]} radius={[4, 4, 0, 0]}>
                <LabelList
                  dataKey="churn_rate"
                  position="top"
                  formatter={(v: any) => `${(Number(v) * 100).toFixed(0)}%`}
                  style={{ fontSize: 10, fill: 'currentColor' }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Delivery velocity */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Delivery velocity by PM team</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="py-2 pr-4 font-semibold">Team</th>
                <th className="py-2 pr-4 font-semibold text-right">Sprints</th>
                <th className="py-2 pr-4 font-semibold text-right">Avg delivered</th>
                <th className="py-2 pr-4 font-semibold text-right">On-time %</th>
                <th className="py-2 font-semibold text-right">Avg slip (days)</th>
              </tr>
            </thead>
            <tbody>
              {data.delivery_velocity.map((d) => (
                <tr
                  key={d.pm_team}
                  className="border-b border-gray-100 dark:border-gray-800"
                >
                  <td className="py-2 pr-4">{d.pm_team}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {d.total_sprints}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {d.avg_delivered}
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {(d.on_time_pct * 100).toFixed(1)}%
                  </td>
                  <td className="py-2 text-right tabular-nums">
                    {d.avg_slip_days}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
