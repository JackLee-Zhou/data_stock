import React from 'react';
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import type { HeatNode } from '../../types/sectorChain';
import { cn } from '../../utils/cn';

interface ChainHeatmapProps {
  nodes: HeatNode[];
  getNodeName: (id: string) => string;
}

const heatColor = (score: number): string => {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 60) return 'bg-emerald-400';
  if (score >= 40) return 'bg-amber-400';
  if (score >= 20) return 'bg-orange-400';
  return 'bg-red-400';
};

const momentumIcon = (m: string) => {
  if (m === 'up') return <ArrowUp className="h-3.5 w-3.5 text-emerald-500" />;
  if (m === 'down') return <ArrowDown className="h-3.5 w-3.5 text-red-500" />;
  return <Minus className="h-3.5 w-3.5 text-secondary-text" />;
};

export const ChainHeatmap: React.FC<ChainHeatmapProps> = ({ nodes, getNodeName }) => {
  if (!nodes || nodes.length === 0) {
    return <p className="text-sm text-secondary-text">暂无热度数据</p>;
  }

  const maxHeat = Math.max(...nodes.map((n) => n.heatScore), 1);

  return (
    <div className="overflow-x-auto">
      <div className="grid grid-cols-[2fr_1fr_1fr_80px] gap-0">
        {/* Header */}
        <div className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-secondary-text border-b border-border">环节</div>
        <div className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-secondary-text border-b border-border text-right">热度</div>
        <div className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-secondary-text border-b border-border text-right">涨跌幅</div>
        <div className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-secondary-text border-b border-border text-center">动量</div>

        {nodes.map((node) => (
          <React.Fragment key={node.nodeId}>
            <div className="px-3 py-2.5 text-sm text-foreground border-b border-border/50 flex items-center gap-2">
              <div className={cn('h-3 w-3 rounded-full flex-shrink-0', heatColor(node.heatScore))} />
              {getNodeName(node.nodeId) || node.nodeId}
            </div>
            <div className="px-3 py-2.5 text-sm border-b border-border/50 text-right">
              <div className="flex items-center justify-end gap-2">
                <div className="h-2 flex-1 max-w-24 rounded-full bg-surface-hover overflow-hidden">
                  <div
                    className={cn('h-full rounded-full transition-all', heatColor(node.heatScore))}
                    style={{ width: `${Math.round((node.heatScore / maxHeat) * 100)}%` }}
                  />
                </div>
                <span className="text-xs tabular-nums font-medium text-foreground">{Math.round(node.heatScore)}</span>
                {node.source === 'ai' && (
                  <span className="text-[10px] text-tertiary-text ml-1" title={node.sourceLabel || 'AI 估算'}>AI</span>
                )}
              </div>
            </div>
            <div className="px-3 py-2.5 text-sm border-b border-border/50 text-right tabular-nums">
              {node.changePct != null ? (
                <span className={cn(
                  'text-xs font-medium',
                  node.changePct > 0 ? 'text-emerald-600' : node.changePct < 0 ? 'text-red-500' : 'text-secondary-text',
                )}>
                  {node.changePct > 0 ? '+' : ''}{node.changePct.toFixed(2)}%
                </span>
              ) : (
                <span className="text-xs text-tertiary-text">-</span>
              )}
            </div>
            <div className="px-3 py-2.5 border-b border-border/50 flex justify-center">
              {momentumIcon(node.momentum)}
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
