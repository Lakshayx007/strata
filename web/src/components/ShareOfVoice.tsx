import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';
import type { Findings } from '../types';
import { vendorLabel, pct, formatNumber, VENDOR_COLORS } from '../utils';

interface ShareOfVoiceProps {
  data: Findings;
}

export default function ShareOfVoice({ data }: ShareOfVoiceProps) {
  const [showTable, setShowTable] = useState(false);
  const chartData = data.share_of_voice.map((v) => ({
    vendor: vendorLabel(v.vendor),
    vendorKey: v.vendor,
    documents: v.documents,
    share: v.share_of_vendor_documents,
    mentions: v.mentions,
    switchingDocs: v.switching_documents,
    label: `${formatNumber(v.documents)} (${pct(v.share_of_vendor_documents)})`,
  }));

  const totalVendorDocs = data.corpus.vendor_documents;

  return (
    <section
      id="share-of-voice"
      className="py-16 px-4"
      aria-labelledby="sov-title"
    >
      <div className="max-w-4xl mx-auto">
        <h2 id="sov-title" className="text-2xl md:text-3xl font-bold mb-2">
          Share of voice
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Discussion documents mentioning each vendor, out of{' '}
          {formatNumber(totalVendorDocs)} that name at least one vendor
          (from {formatNumber(data.corpus.discussion_documents)} total). A
          document can mention multiple vendors.
        </p>

        {!showTable && (
          <div className="h-80 md:h-96" role="img" aria-label="Horizontal bar chart showing share of voice by vendor">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 5, right: 120, left: 10, bottom: 5 }}
              >
                <XAxis type="number" hide />
                <YAxis
                  type="category"
                  dataKey="vendor"
                  width={100}
                  tick={{ fontSize: 14, fill: 'currentColor' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg text-sm">
                        <p className="font-semibold">{d.vendor}</p>
                        <p>Documents: {formatNumber(d.documents)}</p>
                        <p>Share: {pct(d.share)}</p>
                        <p>Mentions: {formatNumber(d.mentions)}</p>
                        <p>Switching docs: {formatNumber(d.switchingDocs)}</p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="documents" radius={[0, 4, 4, 0]} maxBarSize={36}>
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.vendorKey}
                      fill={VENDOR_COLORS[entry.vendorKey] ?? '#6b7280'}
                      stroke={
                        entry.vendorKey === 'cloudera'
                          ? '#d97706'
                          : 'transparent'
                      }
                      strokeWidth={entry.vendorKey === 'cloudera' ? 2 : 0}
                    />
                  ))}
                  <LabelList
                    dataKey="label"
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
              <caption className="sr-only">Share of voice by vendor</caption>
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="py-2 pr-4 font-semibold">Vendor</th>
                  <th className="py-2 pr-4 font-semibold text-right">Documents</th>
                  <th className="py-2 pr-4 font-semibold text-right">Share</th>
                  <th className="py-2 pr-4 font-semibold text-right">Mentions</th>
                  <th className="py-2 font-semibold text-right">Switching docs</th>
                </tr>
              </thead>
              <tbody>
                {data.share_of_voice.map((v) => (
                  <tr
                    key={v.vendor}
                    className={`border-b border-gray-100 dark:border-gray-800 ${
                      v.vendor === 'cloudera'
                        ? 'bg-amber-50 dark:bg-amber-950/30 font-medium'
                        : ''
                    }`}
                  >
                    <td className="py-2 pr-4">{vendorLabel(v.vendor)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {formatNumber(v.documents)}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {pct(v.share_of_vendor_documents)}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {formatNumber(v.mentions)}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {formatNumber(v.switching_documents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-6 text-xs text-gray-500 dark:text-gray-500 space-y-1">
          <p>
            Counts use the corrected Snowflake matcher (idioms such as "special
            snowflake" and snowflake IDs no longer count).
          </p>
          <p>
            <strong>Dev.to caveat:</strong> the Dev.to feeds include tags for
            Databricks, Snowflake, BigQuery and Redshift but none for Cloudera,
            so Cloudera's Dev.to count understates it there.
          </p>
          <p>
            A document can name several vendors, so shares add up to more than
            100%.
          </p>
        </div>
      </div>
    </section>
  );
}
