import { ExternalLink, Quote as QuoteIcon } from 'lucide-react';
import type { Findings } from '../types';
import { categoryLabel, sourceLabel, vendorLabel, formatDate } from '../utils';

interface VoicesProps {
  data: Findings;
}

export default function Voices({ data }: VoicesProps) {
  // The exit_to_open_source case (doc 220) is second-hand
  const secondHandDocIds = new Set([220]);

  return (
    <section id="voices" className="py-16 px-4" aria-labelledby="voices-title">
      <div className="max-w-4xl mx-auto">
        <h2 id="voices-title" className="text-2xl md:text-3xl font-bold mb-2">
          In their words
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-8">
          Verbatim quotes from the labelled sample, exactly as posted.
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          {data.quotes.map((q) => (
            <article
              key={q.document_id}
              className="border border-gray-200 dark:border-gray-800 rounded-xl p-5 hover:border-gray-300 dark:hover:border-gray-700 transition-colors"
            >
              <div className="flex items-start gap-3 mb-3">
                <QuoteIcon
                  size={20}
                  className="text-gray-400 dark:text-gray-600 mt-0.5 shrink-0"
                  aria-hidden="true"
                />
                <blockquote className="text-sm md:text-base leading-relaxed">
                  "{q.quote}"
                </blockquote>
              </div>

              <div className="flex flex-wrap items-center gap-2 mt-3">
                <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-accent/10 text-accent dark:bg-accent-dark/10 dark:text-accent-dark">
                  {categoryLabel(q.category)}
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-500">
                  {sourceLabel(q.source)}
                </span>
                {q.from_vendor !== 'none' && q.to_vendor !== 'none' && (
                  <span className="text-xs text-gray-500 dark:text-gray-500">
                    {vendorLabel(q.from_vendor)} → {vendorLabel(q.to_vendor)}
                  </span>
                )}
                {secondHandDocIds.has(q.document_id) && (
                  <span className="inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                    Second-hand
                  </span>
                )}
                <a
                  href={q.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-accent dark:text-accent-dark hover:underline ml-auto"
                  aria-label={`View original post (document ${q.document_id})`}
                >
                  {formatDate(q.posted_at)}
                  <ExternalLink size={12} />
                </a>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
