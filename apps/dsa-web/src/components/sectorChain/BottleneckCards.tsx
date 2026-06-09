import React from 'react';
import { AlertTriangle } from 'lucide-react';
import type { BottleneckInfo } from '../../types/sectorChain';
import { Card } from '../common';
import { cn } from '../../utils/cn';

interface BottleneckCardsProps {
  bottlenecks: BottleneckInfo[];
  getNodeName: (id: string) => string;
}

const severityMeta: Record<string, { label: string; className: string; desc: string }> = {
  high: { label: '高危', desc: '国产化率 < 30%，高度依赖进口', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  medium: { label: '中危', desc: '国产化率 30-70%，高端仍进口', className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  low: { label: '关注', desc: '国产化率 > 70%，个别规格不足', className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
};

export const BottleneckCards: React.FC<BottleneckCardsProps> = ({ bottlenecks, getNodeName }) => {
  if (!bottlenecks || bottlenecks.length === 0) {
    return <p className="text-sm text-secondary-text">暂无识别的卡脖子环节</p>;
  }

  return (
    <div className="space-y-3">
      {/* 分级说明 */}
      <div className="flex flex-wrap gap-1.5 mb-1">
        {Object.entries(severityMeta).map(([key, meta]) => (
          <span
            key={key}
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs',
              meta.className,
            )}
            title={meta.desc}
          >
            <span className="font-medium">{meta.label}</span>
            <span className="opacity-70 hidden sm:inline">— {meta.desc}</span>
          </span>
        ))}
        <span className="text-xs text-tertiary-text self-center ml-1">AI 基于行业知识判定</span>
      </div>

      {bottlenecks.map((b, i) => {
        const meta = severityMeta[b.severity] || severityMeta.low;
        return (
          <Card key={`${b.nodeId}-${i}`} className="!p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-500" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-foreground text-sm">
                    {getNodeName(b.nodeId) || b.nodeId}
                  </span>
                  <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', meta.className)}>
                    {meta.label}
                  </span>
                </div>
                <p className="text-sm text-secondary-text">{b.description}</p>
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
};
