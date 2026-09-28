import { ExternalLink } from 'lucide-react';
import type { Findings } from '../types';
import { formatDate } from '../utils';

interface FooterProps {
  data: Findings;
}

export default function Footer({ data }: FooterProps) {
  return (
    <footer className="border-t border-gray-200 dark:border-gray-800 py-10 px-4">
      <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-gray-500 dark:text-gray-500">
        <p>
          Built by{' '}
          <span className="font-medium text-gray-700 dark:text-gray-300">
            Lakshay Malik
          </span>
        </p>
        <p>Data last updated: {formatDate(data.generated_at)}</p>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/Lakshayx007/strata"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
            aria-label="GitHub repository"
          >
            <ExternalLink size={14} />
            GitHub
          </a>
          {/* LinkedIn */}
          <a
            href="https://www.linkedin.com/in/lakshaymalik3127"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
            aria-label="LinkedIn profile"
          >
            LinkedIn
            <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </footer>
  );
}
