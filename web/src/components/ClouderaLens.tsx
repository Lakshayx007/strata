import { ExternalLink, AlertTriangle } from 'lucide-react';
import type { Findings } from '../types';
import { sourceLabel, formatNumber, formatDate, kindLabel, pct } from '../utils';

interface ClouderaLensProps {
  data: Findings;
}

export default function ClouderaLens({ data }: ClouderaLensProps) {
  const c = data.cloudera;
  const sovEntry = data.share_of_voice.find((v) => v.vendor === 'cloudera');

  return (
    <section
      id="cloudera"
      className="py-16 px-4 bg-gray-50 dark:bg-gray-900/50"
      aria-labelledby="cloudera-title"
    >
      <div className="max-w-4xl mx-auto">
        <h2
          id="cloudera-title"
          className="text-2xl md:text-3xl font-bold mb-2"
        >
          Cloudera lens
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Nearly absent in public discussion, and what is there is maintenance
          and exit.
        </p>

        {/* Share of voice summary */}
        <div className="grid gap-4 md:grid-cols-3 mb-8">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
            <p className="text-3xl font-bold text-cloudera-highlight">
              {formatNumber(c.documents)}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              documents mention Cloudera
            </p>
          </div>
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
            <p className="text-3xl font-bold text-cloudera-highlight">
              {sovEntry ? pct(sovEntry.share_of_vendor_documents) : '—'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              of vendor-naming documents
            </p>
          </div>
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
            <p className="text-3xl font-bold text-cloudera-highlight">
              {c.labelled_leaving_cloudera}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              labelled as leaving Cloudera
            </p>
          </div>
        </div>

        {/* By source */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-3">Documents by source</h3>
          <div className="flex flex-wrap gap-3">
            {Object.entries(c.by_source).map(([src, count]) => (
              <div
                key={src}
                className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg px-3 py-2 text-sm"
              >
                <span className="font-medium">{sourceLabel(src)}</span>
                <span className="ml-2 text-gray-600 dark:text-gray-400">
                  {count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Cases */}
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Notable documents</h3>
          <div className="space-y-4">
            {c.cases.map((cs) => (
              <article
                key={cs.document_id}
                className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5"
              >
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                    {kindLabel(cs.kind)}
                  </span>
                  <span className="text-xs text-gray-500">
                    {sourceLabel(cs.source)}
                  </span>
                  {cs.kind === 'exit_to_open_source' && (
                    <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                      Second-hand
                    </span>
                  )}
                  <a
                    href={cs.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-accent dark:text-accent-dark hover:underline ml-auto"
                  >
                    {formatDate(cs.posted_at)}
                    <ExternalLink size={12} />
                  </a>
                </div>
                {cs.title && (
                  <p className="font-medium text-sm mb-2">{cs.title}</p>
                )}
                <div className="space-y-2">
                  {cs.quotes.map((q, i) => (
                    <blockquote
                      key={i}
                      className="text-sm text-gray-700 dark:text-gray-300 border-l-2 border-amber-400 pl-3"
                    >
                      "{q}"
                    </blockquote>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>

        {/* What it suggests / can't prove */}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
            <h3 className="text-base font-semibold mb-2 text-green-700 dark:text-green-400">
              What it suggests
            </h3>
            <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
              In public developer discussion, Cloudera appears as an installed
              base being maintained or left, not as a platform being chosen;
              its users' exits go to open-source stacks as well as to cloud
              vendors.
            </p>
          </div>
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-5">
            <h3 className="text-base font-semibold mb-2 flex items-center gap-2">
              <AlertTriangle
                size={16}
                className="text-amber-500"
                aria-hidden="true"
              />
              <span className="text-amber-700 dark:text-amber-400">
                What it can't prove
              </span>
            </h3>
            <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
              The sources lean cloud-native, and on-premises estates are
              discussed less in public, so low share of voice is not low market
              share. Two cases are anecdotes, one of them second-hand. Nothing
              here says anything about Cloudera's licensing or support policy.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
