import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';
import type { Findings } from '../types';
import { categoryLabel, sourceLabel, formatNumber, CHART_COLORS } from '../utils';

interface WhyTeamsSwitchProps {
  data: Findings;
}

type SourceFilter = 'all' | 'hackernews' | 'stackexchange' | 'devto';

export default function WhyTeamsSwitch({ data }: WhyTeamsSwitchProps) {
  const [source, setSource] = useState<SourceFilter>('all');
  const [excludePromo, setExcludePromo] = useState(false);
  const [showTable, setShowTable] = useState(false);

  const sources: SourceFilter[] = ['all', 'hackernews', 'stackexchange', 'devto'];

  // Check if source has data
  const sourceHasData = (s: SourceFilter): boolean => {
    if (s === 'all') return true;
    const sourceInfo = data.reasons.by_source.find((bs) => bs.source === s);
    return (sourceInfo?.with_reason ?? 0) > 0;
  };

  // Build chart data based on filters
  const getChartData = () => {
    if (source === 'all' && excludePromo) {
      // Use promotional_sensitivity data
      return data.promotional_sensitivity.all_samples.by_category.map((cat) => ({
        category: categoryLabel(cat.category),
        count: cat.without,
      }));
    }

    if (source === 'all' && !excludePromo) {
      return data.reasons.by_category.map((cat) => ({
        category: categoryLabel(cat.category),
        count: cat.reasons,
      }));
    }

    // Filter by source — promotional filter not available per-source
    if (source !== 'all') {
      return data.reasons.by_category
        .map((cat) => ({
          category: categoryLabel(cat.category),
          count: cat.by_source[source] ?? 0,
        }))
        .filter((d) => d.count > 0);
    }

    return [];
  };

  const chartData = getChartData();
  const totalReasons = excludePromo
    ? data.promotional_sensitivity.all_samples.reasons_without
    : source === 'all'
    ? data.reasons.reasons_total
    : chartData.reduce((sum, d) => sum + d.count, 0);

  // Promo toggle only available for "all" source
  const promoToggleAvailable = source === 'all';

  return (
    <section
      id="why-teams-switch"
      className="py-16 px-4 bg-gray-50 dark:bg-gray-900/50"
      aria-labelledby="switch-title"
    >
      <div className="max-w-4xl mx-auto">
        <h2 id="switch-title" className="text-2xl md:text-3xl font-bold mb-2">
          Why teams switch
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Reason categories from {formatNumber(data.reasons.documents_labelled)}{' '}
          labelled documents.{' '}
          <span className="font-medium">
            {formatNumber(totalReasons)} reasons
          </span>{' '}
          identified.
        </p>

        {/* Controls */}
        <div className="flex flex-wrap gap-4 mb-6">
          <fieldset className="flex flex-wrap gap-2" aria-label="Source filter">
            {sources.map((s) => {
              const hasData = sourceHasData(s);
              return (
                <button
                  key={s}
                  onClick={() => {
                    setSource(s);
                    if (s !== 'all') setExcludePromo(false);
                  }}
                  disabled={!hasData}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                    source === s
                      ? 'bg-accent text-white border-accent dark:bg-accent-dark dark:border-accent-dark'
                      : hasData
                      ? 'border-gray-300 dark:border-gray-600 hover:border-accent dark:hover:border-accent-dark'
                      : 'border-gray-200 dark:border-gray-700 text-gray-400 dark:text-gray-600 cursor-not-allowed'
                  }`}
                  aria-pressed={source === s}
                >
                  {s === 'all' ? 'All' : sourceLabel(s)}
                </button>
              );
            })}
          </fieldset>

          <label
            className={`inline-flex items-center gap-2 text-sm ${
              !promoToggleAvailable
                ? 'text-gray-400 dark:text-gray-600 cursor-not-allowed'
                : 'cursor-pointer'
            }`}
          >
            <input
              type="checkbox"
              checked={excludePromo}
              onChange={(e) => setExcludePromo(e.target.checked)}
              disabled={!promoToggleAvailable}
              className="rounded border-gray-300 dark:border-gray-600 text-accent dark:text-accent-dark focus:ring-accent"
            />
            Exclude promotional posts
            <span className="text-xs text-gray-500">
              ({data.promotional_sensitivity.all_samples.flagged_with_reason}{' '}
              flagged)
            </span>
          </label>
        </div>

        {chartData.length === 0 ? (
          <p className="text-gray-500 py-8 text-center">
            No reasons available for this source.
          </p>
        ) : (
          <>
            {!showTable && (
              <div className="h-80 md:h-96" role="img" aria-label="Horizontal bar chart of reason categories">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{ top: 5, right: 80, left: 10, bottom: 5 }}
                  >
                    <XAxis type="number" hide />
                    <YAxis
                      type="category"
                      dataKey="category"
                      width={160}
                      tick={{ fontSize: 13, fill: 'currentColor' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload;
                        return (
                          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg text-sm">
                            <p className="font-semibold">{d.category}</p>
                            <p>Count: {d.count}</p>
                            <p>
                              Share: {((d.count / totalReasons) * 100).toFixed(1)}%
                            </p>
                          </div>
                        );
                      }}
                    />
                    <Bar
                      dataKey="count"
                      fill={CHART_COLORS[0]}
                      radius={[0, 4, 4, 0]}
                      maxBarSize={32}
                    >
                      <LabelList
                        dataKey="count"
                        position="right"
                        style={{ fontSize: 13, fill: 'currentColor' }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            <button
              onClick={() => setShowTable((s) => !s)}
              className="mt-4 text-sm text-accent dark:text-accent-dark hover:underline"
            >
              {showTable ? 'Show as chart' : 'Show as table'}
            </button>

            {showTable && (
              <div className="overflow-x-auto mt-4">
                <table className="w-full text-sm text-left" role="table">
                  <caption className="sr-only">
                    Reason categories with counts
                  </caption>
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="py-2 pr-4 font-semibold">Category</th>
                      <th className="py-2 pr-4 font-semibold text-right">
                        Count
                      </th>
                      <th className="py-2 font-semibold text-right">
                        Share of {totalReasons}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {chartData.map((d) => (
                      <tr
                        key={d.category}
                        className="border-b border-gray-100 dark:border-gray-800"
                      >
                        <td className="py-2 pr-4">{d.category}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {d.count}
                        </td>
                        <td className="py-2 text-right tabular-nums">
                          {totalReasons > 0
                            ? ((d.count / totalReasons) * 100).toFixed(1) + '%'
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        <p className="mt-6 text-xs text-gray-500 dark:text-gray-500">
          Stack Exchange contributes almost no reasons (1 of{' '}
          {data.reasons.by_source.find((s) => s.source === 'stackexchange')
            ?.documents ?? '—'}{' '}
          labelled documents), so the reason mix is mostly Hacker News and
          Dev.to voices.
        </p>
      </div>
    </section>
  );
}
