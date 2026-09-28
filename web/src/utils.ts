// Display helpers — no data logic, just formatting

const CATEGORY_LABELS: Record<string, string> = {
  cost: 'Cost',
  operational_simplicity: 'Operational simplicity',
  lock_in_openness: 'Lock-in & openness',
  performance_scale: 'Performance & scale',
  right_sizing: 'Right-sizing',
  ecosystem_fit: 'Ecosystem fit',
  governance_security: 'Governance & security',
  other: 'Other',
  none: 'No reason given',
};

const SOURCE_LABELS: Record<string, string> = {
  hackernews: 'Hacker News',
  stackexchange: 'Stack Exchange',
  devto: 'Dev.to',
  github_threads: 'GitHub',
};

const VENDOR_LABELS: Record<string, string> = {
  snowflake: 'Snowflake',
  databricks: 'Databricks',
  google: 'Google',
  aws: 'AWS',
  microsoft: 'Microsoft',
  cloudera: 'Cloudera',
  other: 'Other',
  none: 'None',
};

const KIND_LABELS: Record<string, string> = {
  stranded_on_free_edition: 'Stranded on free edition',
  exit_to_open_source: 'Exit to open source',
  legacy_reference: 'Legacy reference',
};

export function categoryLabel(code: string): string {
  return CATEGORY_LABELS[code] ?? code;
}

export function sourceLabel(code: string): string {
  return SOURCE_LABELS[code] ?? code;
}

export function vendorLabel(code: string): string {
  return VENDOR_LABELS[code] ?? code;
}

export function kindLabel(code: string): string {
  return KIND_LABELS[code] ?? code;
}

export function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

// Accessible chart colours (colourblind-friendly palette)
export const CHART_COLORS = [
  '#3b82f6', // blue
  '#10b981', // emerald
  '#8b5cf6', // violet
  '#f59e0b', // amber
  '#ef4444', // red
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#6b7280', // gray
];

export const VENDOR_COLORS: Record<string, string> = {
  snowflake: '#29b5e8',
  databricks: '#ff3621',
  google: '#4285f4',
  aws: '#ff9900',
  microsoft: '#00a4ef',
  cloudera: '#f59e0b',
};
