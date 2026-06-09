import React from 'react';
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';
import type { FuturesQuote } from '../../types/futures';
import { cn } from '../../utils/cn';

interface FuturesTableProps {
  items: FuturesQuote[];
}

const formatNum = (v: number | undefined | null, decimals = 2): string => {
  if (v === undefined || v === null) return '-';
  return v.toFixed(decimals);
};

const formatVolume = (v: number): string => {
  if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
  return String(v);
};

const ChangeCell: React.FC<{ value: number }> = ({ value }) => {
  const icon =
    value > 0 ? <ArrowUp className="inline-block h-3 w-3" /> : value < 0 ? <ArrowDown className="inline-block h-3 w-3" /> : <Minus className="inline-block h-3 w-3" />;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-xs font-medium tabular-nums',
        value > 0 && 'text-emerald-600 dark:text-emerald-400',
        value < 0 && 'text-red-600 dark:text-red-400',
        value === 0 && 'text-secondary-text',
      )}
    >
      {icon}
      {formatNum(value)}%
    </span>
  );
};

export const FuturesTable: React.FC<FuturesTableProps> = ({ items }) => {
  const HEADER_CLASS = 'px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-secondary-text';

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className={HEADER_CLASS}>合约</th>
            <th className={cn(HEADER_CLASS, 'text-right')}>最新价</th>
            <th className={cn(HEADER_CLASS, 'text-right')}>涨跌额</th>
            <th className={cn(HEADER_CLASS, 'text-right')}>涨跌幅</th>
            <th className={cn(HEADER_CLASS, 'text-right hidden md:table-cell')}>成交量</th>
            <th className={cn(HEADER_CLASS, 'text-right hidden md:table-cell')}>持仓量</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => (
            <tr
              key={item.contractCode}
              className="transition-colors hover:bg-surface-hover"
            >
              <td className="px-3 py-2.5">
                <div className="font-medium text-foreground">{item.contractName}</div>
                <div className="text-xs text-secondary-text">{item.contractCode}</div>
              </td>
              <td className="px-3 py-2.5 text-right font-mono font-medium tabular-nums text-foreground">
                {formatNum(item.lastPrice, item.lastPrice < 10 ? 4 : 2)}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                <span
                  className={cn(
                    'text-xs',
                    item.change > 0 && 'text-emerald-600 dark:text-emerald-400',
                    item.change < 0 && 'text-red-600 dark:text-red-400',
                    item.change === 0 && 'text-secondary-text',
                  )}
                >
                  {item.change > 0 ? '+' : ''}{formatNum(item.change)}
                </span>
              </td>
              <td className="px-3 py-2.5 text-right">
                <ChangeCell value={item.changePct} />
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-secondary-text hidden md:table-cell">
                {item.volume > 0 ? formatVolume(item.volume) : '-'}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-secondary-text hidden md:table-cell">
                {item.openInterest > 0 ? formatVolume(item.openInterest) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
