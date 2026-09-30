interface CompetitivePanelProps {
  data: {
    vendors: string[];
    capabilities: string[];
    groups: string[];
    scores: Array<{
      vendor: string;
      capability: string;
      group: string;
      score: number;
      evidence_url: string | null;
      note: string | null;
    }>;
    group_scores: Record<string, Record<string, number>>;
    positioning: Array<{
      vendor: string;
      deploy_flex: number;
      openness: number;
    }>;
  };
}

const SCORE_COLORS: Record<number, string> = {
  0: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  1: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  2: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
};

const SCORE_LABELS: Record<number, string> = {
  0: 'Not offered',
  1: 'Partial/Preview',
  2: 'GA Native',
};

export default function CompetitivePanel({ data }: CompetitivePanelProps) {
  const vendors = data.vendors;

  // Group capabilities
  const groupedCaps: Record<string, string[]> = {};
  for (const s of data.scores) {
    if (!groupedCaps[s.group]) groupedCaps[s.group] = [];
    if (!groupedCaps[s.group].includes(s.capability)) {
      groupedCaps[s.group].push(s.capability);
    }
  }

  const getScore = (vendor: string, cap: string) => {
    const s = data.scores.find(
      (r) => r.vendor === vendor && r.capability === cap
    );
    return s?.score ?? null;
  };

  const getNote = (vendor: string, cap: string) => {
    const s = data.scores.find(
      (r) => r.vendor === vendor && r.capability === cap
    );
    return s?.note ?? null;
  };

  return (
    <div className="space-y-8">
      {/* Heatmap table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead>
            <tr className="border-b-2 border-gray-300 dark:border-gray-600">
              <th className="py-2 pr-2 font-semibold sticky left-0 bg-gray-50 dark:bg-gray-900/50">
                Capability
              </th>
              {vendors.map((v) => (
                <th key={v} className="py-2 px-2 font-semibold text-center capitalize">
                  {v}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(groupedCaps).map(([group, caps]) => (
              <>
                <tr key={`group-${group}`}>
                  <td
                    colSpan={vendors.length + 1}
                    className="py-1.5 text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-500 bg-gray-100 dark:bg-gray-800"
                  >
                    {group.replace(/_/g, ' ')}
                  </td>
                </tr>
                {caps.map((cap) => (
                  <tr
                    key={cap}
                    className="border-b border-gray-100 dark:border-gray-800"
                  >
                    <td className="py-1.5 pr-2 font-mono text-xs sticky left-0 bg-white dark:bg-gray-950">
                      {cap.replace(/_/g, ' ')}
                    </td>
                    {vendors.map((v) => {
                      const score = getScore(v, cap);
                      const note = getNote(v, cap);
                      return (
                        <td key={v} className="py-1.5 px-2 text-center">
                          {score !== null ? (
                            <span
                              className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${
                                SCORE_COLORS[score] ?? ''
                              }`}
                              title={note ?? SCORE_LABELS[score] ?? ''}
                            >
                              {score}
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-gray-500">
        0 = not offered · 1 = partial, preview, or via partner · 2 = GA native.
        Hover a score for its note.
      </p>

      {/* Positioning map as data */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Positioning map</h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          X = deployment flexibility (mean of on-prem, private cloud, multi-cloud,
          sovereign, single control plane). Y = openness / interoperability (mean
          of Iceberg, Delta, REST catalog, cross-system lineage).
        </p>
        <div className="grid gap-3 md:grid-cols-3">
          {data.positioning
            .sort((a, b) => b.deploy_flex + b.openness - (a.deploy_flex + a.openness))
            .map((p) => (
              <div
                key={p.vendor}
                className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-3"
              >
                <p className="font-medium capitalize">{p.vendor}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Deploy: {p.deploy_flex.toFixed(1)} · Open: {p.openness.toFixed(1)}
                </p>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
