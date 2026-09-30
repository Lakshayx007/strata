import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LabelList,
  Cell,
} from 'recharts';
import { CHART_COLORS } from '../utils';

interface MarketPanelProps {
  data: {
    total_2025: number;
    total_2030: number;
    overall_cagr: number;
    workloads_2025: Record<string, number>;
    workloads_2030: Record<string, number>;
    deployments_2025: Record<string, number>;
    deployments_2030: Record<string, number>;
    assumptions: Array<{
      key: string;
      value: number;
      type: string;
      source_url: string | null;
      rationale: string | null;
    }>;
  };
}

export default function MarketPanel({ data }: MarketPanelProps) {
  const [showTable, setShowTable] = useState(false);

  const workloadData = Object.entries(data.workloads_2030)
    .map(([name, val], i) => ({
      name,
      '2025': data.workloads_2025[name] ?? 0,
      '2030': val,
      fill: CHART_COLORS[i % CHART_COLORS.length],
    }))
    .sort((a, b) => b['2030'] - a['2030']);

  const deployData = Object.entries(data.deployments_2030).map(
    ([name, val]) => ({
      name,
      '2025': data.deployments_2025[name] ?? 0,
      '2030': val,
    })
  );

  return (
    <div className="space-y-8">
      {/* Headline stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
          <p className="text-3xl font-bold text-accent dark:text-accent-dark">
            ${(data.total_2025 / 1e9).toFixed(1)}B
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            2025 market size (bottom-up)
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
          <p className="text-3xl font-bold text-accent dark:text-accent-dark">
            ${(data.total_2030 / 1e9).toFixed(1)}B
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            2030 forecast
          </p>
        </div>
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
          <p className="text-3xl font-bold text-accent dark:text-accent-dark">
            {(data.overall_cagr * 100).toFixed(1)}%
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Overall CAGR
          </p>
        </div>
      </div>

      {/* Stacked bar: 2025→2030 by workload */}
      <div>
        <h3 className="text-lg font-semibold mb-4">
          Market size by workload (2025 → 2030)
        </h3>
        {!showTable && (
          <div className="h-80" role="img" aria-label="Bar chart of market size by workload">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={workloadData}
                layout="vertical"
                margin={{ top: 5, right: 100, left: 10, bottom: 5 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={160}
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
                        <p className="font-semibold">{d.name}</p>
                        <p>2025: ${(d['2025'] / 1e9).toFixed(1)}B</p>
                        <p>2030: ${(d['2030'] / 1e9).toFixed(1)}B</p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="2030" radius={[0, 4, 4, 0]} maxBarSize={32}>
                  {workloadData.map((entry, i) => (
                    <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                  <LabelList
                    dataKey="2030"
                    position="right"
                    formatter={(v: any) => `$${(Number(v) / 1e9).toFixed(1)}B`}
                    style={{ fontSize: 12, fill: 'currentColor' }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        <button
          onClick={() => setShowTable((s) => !s)}
          className="mt-2 text-sm text-accent dark:text-accent-dark hover:underline"
        >
          {showTable ? 'Show as chart' : 'Show as table'}
        </button>
        {showTable && (
          <div className="overflow-x-auto mt-4">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="py-2 pr-4 font-semibold">Workload</th>
                  <th className="py-2 pr-4 font-semibold text-right">2025</th>
                  <th className="py-2 font-semibold text-right">2030</th>
                </tr>
              </thead>
              <tbody>
                {workloadData.map((d) => (
                  <tr key={d.name} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 pr-4">{d.name}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      ${(d['2025'] / 1e9).toFixed(1)}B
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      ${(d['2030'] / 1e9).toFixed(1)}B
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Deployment share */}
      <div>
        <h3 className="text-lg font-semibold mb-4">Deployment-mode share</h3>
        <div className="grid gap-3 md:grid-cols-3">
          {deployData.map((d) => (
            <div
              key={d.name}
              className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-3"
            >
              <p className="font-medium text-sm">{d.name}</p>
              <p className="text-lg font-bold">
                ${(d['2030'] / 1e9).toFixed(1)}B
              </p>
              <p className="text-xs text-gray-500">
                from ${(d['2025'] / 1e9).toFixed(1)}B in 2025
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Assumptions */}
      <details className="text-sm">
        <summary className="cursor-pointer font-semibold text-accent dark:text-accent-dark">
          View all assumptions ({data.assumptions.length} inputs)
        </summary>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="py-1 pr-2">Input</th>
                <th className="py-1 pr-2">Value</th>
                <th className="py-1 pr-2">Type</th>
                <th className="py-1">Source / Rationale</th>
              </tr>
            </thead>
            <tbody>
              {data.assumptions.map((a) => (
                <tr key={a.key} className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-1 pr-2 font-mono">{a.key}</td>
                  <td className="py-1 pr-2 tabular-nums">{a.value}</td>
                  <td className="py-1 pr-2">
                    <span
                      className={`px-1 py-0.5 rounded text-xs ${
                        a.type === 'SOURCED'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}
                    >
                      {a.type}
                    </span>
                  </td>
                  <td className="py-1">
                    {a.source_url ? (
                      <a
                        href={a.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent dark:text-accent-dark hover:underline"
                      >
                        {a.rationale ?? 'Source'}
                      </a>
                    ) : (
                      a.rationale ?? '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
