import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import type { AvailableSector } from '../../types/sectorChain';
import { Button, Loading } from '../common';

interface SectorSearchSelectProps {
  sectors: AvailableSector[];
  loading: boolean;
  disabled: boolean;
  onAnalyze: (name: string) => void;
}

export const SectorSearchSelect: React.FC<SectorSearchSelectProps> = ({
  sectors,
  loading,
  disabled,
  onAnalyze,
}) => {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sectors.slice(0, 20);
    return sectors
      .filter((s) => s.name.toLowerCase().includes(q))
      .slice(0, 20);
  }, [sectors, query]);

  const trimmed = query.trim();
  // 按钮可用条件：输入了内容 且 没在加载中
  const canAnalyze = trimmed.length > 0 && !disabled;

  const handleSubmit = () => {
    if (!canAnalyze) return;
    onAnalyze(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && canAnalyze) {
      handleSubmit();
    }
  };

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-secondary-text" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入板块名称，如 半导体、新能源车、光伏…（支持自由输入，回车即可分析）"
          disabled={disabled}
          className="w-full rounded-xl border border-border bg-surface py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-tertiary-text focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
        />
      </div>

      {loading && <Loading label="加载板块列表…" />}

      {/* 下拉提示：仅在没有加载且无匹配时展示快捷入口 */}
      {!loading && query.trim() && filtered.length > 0 && (
        <div className="max-h-48 overflow-y-auto rounded-xl border border-border">
          {filtered.map((sector) => (
            <button
              key={sector.name}
              type="button"
              onClick={() => { setQuery(sector.name); }}
              className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors hover:bg-surface-hover text-foreground"
            >
              <span>{sector.name}</span>
              {sector.changePct != null && (
                <span className={`text-xs tabular-nums ${
                  sector.changePct > 0 ? 'text-emerald-600' : sector.changePct < 0 ? 'text-red-500' : 'text-secondary-text'
                }`}>
                  {sector.changePct > 0 ? '+' : ''}{sector.changePct.toFixed(2)}%
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      {!loading && query.trim() && filtered.length === 0 && (
        <p className="text-sm text-secondary-text">
          列表中未匹配「{trimmed}」，将直接作为板块名分析（取决于数据源是否支持）
        </p>
      )}

      <Button
        variant="primary"
        size="lg"
        disabled={!canAnalyze}
        isLoading={disabled}
        onClick={handleSubmit}
        className="w-full"
      >
        {disabled
          ? 'AI 分析中…'
          : trimmed
            ? `分析「${trimmed}」产业链`
            : '输入板块名称开始分析'}
      </Button>
    </div>
  );
};
