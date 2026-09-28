import { AlertTriangle } from 'lucide-react';
import type { Findings } from '../types';

interface HowItWasBuiltProps {
  data: Findings;
}

const PIPELINE_STEPS = [
  { label: 'Sources', desc: 'HN, SE, Dev.to, GitHub' },
  { label: 'Ingest', desc: 'Official APIs only' },
  { label: 'Dedupe', desc: 'Exact + near-duplicate' },
  { label: 'Switching detector', desc: 'v1 phrases + v2 sentences' },
  { label: 'Stratified sample', desc: '300 documents, two seeds' },
  { label: 'Model draft labels', desc: 'First-pass labelling' },
  { label: 'Second-model review', desc: 'Claude review of excerpts' },
  { label: 'Export', desc: 'findings.json' },
];

export default function HowItWasBuilt({ data }: HowItWasBuiltProps) {
  // Get agreement data for the detector comparison display
  const seedV1TaxAgreement = data.agreement.find(
    (a) => a.sample === 'seed_v1' && a.field === 'taxonomy_code'
  );
  const seedV2TaxAgreement = data.agreement.find(
    (a) => a.sample === 'seed_v2' && a.field === 'taxonomy_code'
  );

  return (
    <section
      id="how-it-was-built"
      className="py-16 px-4"
      aria-labelledby="built-title"
    >
      <div className="max-w-4xl mx-auto">
        <h2 id="built-title" className="text-2xl md:text-3xl font-bold mb-8">
          How it was built
        </h2>

        {/* Pipeline diagram */}
        <div className="mb-10">
          <h3 className="text-lg font-semibold mb-4">Pipeline</h3>
          <div className="flex flex-wrap items-center gap-2 md:gap-0">
            {PIPELINE_STEPS.map((step, i) => (
              <div key={step.label} className="flex items-center">
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg px-3 py-2 text-center min-w-[100px]">
                  <p className="text-sm font-medium">{step.label}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-500">
                    {step.desc}
                  </p>
                </div>
                {i < PIPELINE_STEPS.length - 1 && (
                  <span
                    className="text-gray-400 dark:text-gray-600 mx-1 text-lg"
                    aria-hidden="true"
                  >
                    →
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Detector precision comparison */}
        <div className="mb-10">
          <h3 className="text-lg font-semibold mb-4">
            Switching detector precision
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Measured on seed_v1 (150 documents, 33 with a reason or move per
            claude_review labels):
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left" role="table">
              <caption className="sr-only">Detector comparison</caption>
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="py-2 pr-4 font-semibold">Detector</th>
                  <th className="py-2 pr-4 font-semibold text-right">
                    Flagged
                  </th>
                  <th className="py-2 pr-4 font-semibold text-right">
                    True positives
                  </th>
                  <th className="py-2 pr-4 font-semibold text-right">
                    Precision
                  </th>
                  <th className="py-2 font-semibold text-right">Recall</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-2 pr-4">v1 phrase list</td>
                  <td className="py-2 pr-4 text-right tabular-nums">110</td>
                  <td className="py-2 pr-4 text-right tabular-nums">27</td>
                  <td className="py-2 pr-4 text-right tabular-nums">24.5%</td>
                  <td className="py-2 text-right tabular-nums">81.8%</td>
                </tr>
                <tr className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-2 pr-4">
                    v2 platform + move/reason sentence
                  </td>
                  <td className="py-2 pr-4 text-right tabular-nums">84</td>
                  <td className="py-2 pr-4 text-right tabular-nums">27</td>
                  <td className="py-2 pr-4 text-right tabular-nums">32.1%</td>
                  <td className="py-2 text-right tabular-nums">81.8%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            v2 was tuned on seed_v1, so its seed_v1 precision is optimistic.
            Labels are model-vs-model, not human.
          </p>
        </div>

        {/* Agreement stats */}
        <div className="mb-10">
          <h3 className="text-lg font-semibold mb-4">
            Model-vs-model agreement
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {seedV1TaxAgreement && (
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  seed_v1 — reason code
                </p>
                <p className="text-2xl font-bold">
                  {(seedV1TaxAgreement.pct_agree * 100).toFixed(1)}%
                </p>
                <p className="text-sm text-gray-500">
                  κ = {seedV1TaxAgreement.cohen_kappa.toFixed(2)} (n ={' '}
                  {seedV1TaxAgreement.n})
                </p>
              </div>
            )}
            {seedV2TaxAgreement && (
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  seed_v2 — reason code
                </p>
                <p className="text-2xl font-bold">
                  {(seedV2TaxAgreement.pct_agree * 100).toFixed(1)}%
                </p>
                <p className="text-sm text-gray-500">
                  κ = {seedV2TaxAgreement.cohen_kappa.toFixed(2)} (n ={' '}
                  {seedV2TaxAgreement.n})
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Limitations box */}
        <div className="border-2 border-amber-400 dark:border-amber-600 rounded-xl p-6 bg-amber-50 dark:bg-amber-950/20">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle
              size={20}
              className="text-amber-600 dark:text-amber-400"
              aria-hidden="true"
            />
            Limitations
          </h3>
          <ul className="space-y-2 text-sm leading-relaxed text-gray-800 dark:text-gray-200">
            <li>
              <strong>No human review.</strong> Every label is a model draft
              plus a second-model review of excerpts. There is no ground truth.
            </li>
            <li>
              <strong>Agreement is model-vs-model:</strong>{' '}
              {seedV1TaxAgreement
                ? `${(seedV1TaxAgreement.pct_agree * 100).toFixed(1)}%`
                : '—'}{' '}
              on reason code for seed_v1 (κ{' '}
              {seedV1TaxAgreement
                ? seedV1TaxAgreement.cohen_kappa.toFixed(2)
                : '—'}
              ) and{' '}
              {seedV2TaxAgreement
                ? `${(seedV2TaxAgreement.pct_agree * 100).toFixed(1)}%`
                : '—'}{' '}
              for seed_v2 (κ{' '}
              {seedV2TaxAgreement
                ? seedV2TaxAgreement.cohen_kappa.toFixed(2)
                : '—'}
              ). It measures consistency between two similar passes, not
              accuracy.
            </li>
            <li>
              <strong>Small n.</strong>{' '}
              {data.reasons.reasons_total} reasons in{' '}
              {data.reasons.documents_labelled} documents; categories below
              about 10 cannot be ranked against each other.
            </li>
            <li>
              <strong>Source bias.</strong> Stack Exchange gives almost no
              reasons (1 of{' '}
              {data.reasons.by_source.find(
                (s) => s.source === 'stackexchange'
              )?.documents ?? '—'}{' '}
              labelled documents), so the reason mix is mostly Hacker News and
              Dev.to voices. Reddit, G2, Gartner Peer Insights and TrustRadius
              are not in the corpus.
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}
