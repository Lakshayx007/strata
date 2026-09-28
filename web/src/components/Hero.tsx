import { ExternalLink, FileText } from 'lucide-react';
import type { Findings } from '../types';
import { formatNumber } from '../utils';

interface HeroProps {
  data: Findings;
}

export default function Hero({ data }: HeroProps) {
  const topCategory = data.reasons.by_category[0];
  const totalReasons = data.reasons.reasons_total;
  const corpusSize = data.corpus.discussion_documents;

  return (
    <section className="py-16 md:py-24 px-4" aria-labelledby="hero-title">
      <div className="max-w-3xl mx-auto text-center">
        <h1
          id="hero-title"
          className="text-4xl md:text-5xl font-bold tracking-tight mb-4"
        >
          Strata
        </h1>
        <p className="text-xl md:text-2xl text-gray-600 dark:text-gray-400 mb-8">
          Why do teams choose or leave data platforms?
        </p>

        <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-6 md:p-8 mb-8 text-left border border-gray-200 dark:border-gray-800">
          <p className="text-lg md:text-xl leading-relaxed">
            <span className="font-semibold text-accent dark:text-accent-dark">
              {topCategory.category === 'cost' ? 'Cost' : topCategory.category}
            </span>{' '}
            is the most common stated reason for a data-platform choice —{' '}
            <span className="font-semibold">
              {topCategory.reasons} of {totalReasons}
            </span>{' '}
            reasons in {formatNumber(data.reasons.documents_labelled)} labelled
            documents, drawn from a corpus of{' '}
            <span className="font-semibold">
              {formatNumber(corpusSize)}
            </span>{' '}
            public developer discussions across Hacker News, Stack Exchange,
            and Dev.to.
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-500 mt-3">
            Labels are model-draft plus second-model review. No label is
            human-reviewed.
          </p>
        </div>

        <div className="flex flex-wrap justify-center gap-4">
          <a
            href="https://github.com/Lakshayx007/strata/blob/main/docs/findings.md"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm font-medium text-accent dark:text-accent-dark hover:underline"
          >
            <FileText size={16} />
            Findings brief
          </a>
          <a
            href="https://github.com/Lakshayx007/strata/blob/main/docs/methodology.md"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm font-medium text-accent dark:text-accent-dark hover:underline"
          >
            <FileText size={16} />
            Methodology
          </a>
          <a
            href="https://github.com/Lakshayx007/strata"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm font-medium text-accent dark:text-accent-dark hover:underline"
          >
            <ExternalLink size={14} />
            View on GitHub
          </a>
        </div>
      </div>
    </section>
  );
}
