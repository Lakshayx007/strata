import { useState } from 'react';
import MarketPanel from './MarketPanel';
import CompetitivePanel from './CompetitivePanel';
import PipelinePanel from './PipelinePanel';

type Tab = 'market' | 'competitive' | 'pipeline';

interface MarketAndPipelineProps {
  marketData: any;
  competitiveData: any;
  pipelineData: any;
}

export default function MarketAndPipeline({
  marketData,
  competitiveData,
  pipelineData,
}: MarketAndPipelineProps) {
  const [tab, setTab] = useState<Tab>('market');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'market', label: 'Market model' },
    { key: 'competitive', label: 'Competitive matrix' },
    { key: 'pipeline', label: 'Pipeline analytics' },
  ];

  return (
    <section
      id="market-pipeline"
      className="py-16 px-4"
      aria-labelledby="mp-title"
    >
      <div className="max-w-5xl mx-auto">
        <h2 id="mp-title" className="text-2xl md:text-3xl font-bold mb-2">
          Market &amp; Pipeline
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          Phase 3: market sizing, competitive analysis, and simulated pipeline
          analytics.
        </p>

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 border-b border-gray-200 dark:border-gray-800">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === t.key
                  ? 'border-accent text-accent dark:border-accent-dark dark:text-accent-dark'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
              }`}
              aria-pressed={tab === t.key}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Panels */}
        {tab === 'market' && <MarketPanel data={marketData} />}
        {tab === 'competitive' && <CompetitivePanel data={competitiveData} />}
        {tab === 'pipeline' && <PipelinePanel data={pipelineData} />}
      </div>
    </section>
  );
}
