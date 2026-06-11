import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, TrendingUp } from 'lucide-react';
import { futuresApi } from '../api/futures';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { AppPage, PageHeader, SectionCard, Loading, EmptyState } from '../components/common';
import { CtpStatusBar } from '../components/ctp/CtpStatusBar';
import type { FuturesQuote } from '../types/futures';
import { FuturesTable } from '../components/futures/FuturesTable';
import { FuturesDetail } from '../components/futures/FuturesDetail';

type Tab = 'domestic' | 'international';

const FuturesPage: React.FC = () => {
  const { t } = useUiLanguage();
  const [tab, setTab] = useState<Tab>('domestic');
  const [items, setItems] = useState<FuturesQuote[]>([]);
  const [allItems, setAllItems] = useState<FuturesQuote[]>([]);
  const [updatedAt, setUpdatedAt] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<FuturesQuote | null>(null);
  const [search, setSearch] = useState('');

  const fetchAll = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const data = await futuresApi.getQuotes();
      setAllItems(data.items);
      setUpdatedAt(data.updatedAt);
    } catch (e: any) { setError(e?.message || '加载失败'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);
  useEffect(() => { document.title = `${t('layout.nav.futures')} — DSA`; }, [t]);

  useEffect(() => {
    setItems(allItems.filter(i => i.market === tab));
  }, [tab, allItems]);

  // 搜索过滤
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(i =>
      i.contractCode.toLowerCase().includes(q) ||
      i.contractName.toLowerCase().includes(q)
    );
  }, [items, search]);

  useEffect(() => {
    // 切换 tab 或搜索时清除选中
    setSelected(null);
  }, [tab, search]);

  return (
    <AppPage className="space-y-5">
      <CtpStatusBar />
      <PageHeader title={t('layout.nav.futures')} description="国内期货实时行情 · CTP SimNow Group2 · 点击合约查看K线" />

      {/* Tabs */}
      <div className="flex items-center gap-2">
        {[['domestic', '国内期货']].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key as Tab)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${tab === key ? 'bg-accent text-white' : 'bg-surface-hover text-secondary-text hover:text-foreground'}`}>
            {label}
          </button>
        ))}
        {updatedAt && <span className="ml-auto text-xs text-tertiary-text">更新: {new Date(updatedAt).toLocaleTimeString('zh-CN')}</span>}
      </div>

      {loading && <Loading label="加载期货行情…" />}
      {!loading && error && <SectionCard title="加载失败"><p className="text-sm text-red-500">{error}</p></SectionCard>}
      {!loading && !error && items.length === 0 && <EmptyState icon={<TrendingUp className="h-10 w-10" />} title="暂无数据" />}

      {!loading && !error && items.length > 0 && (
        <>
          {/* 合约列表卡片（固定高度+滚动+搜索） */}
          <SectionCard
            title={`${tab === 'domestic' ? '国内' : '国际'}合约 (${filtered.length})`}
            actions={
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-tertiary-text" />
                <input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="搜索合约…"
                  className="w-44 rounded-lg border border-border bg-surface py-1.5 pl-8 pr-3 text-xs text-foreground placeholder:text-tertiary-text focus:border-accent focus:outline-none"
                />
              </div>
            }
          >
            <div className="max-h-[360px] overflow-y-auto">
              <FuturesTable items={filtered} onSelect={setSelected} selected={selected?.contractCode} />
            </div>
          </SectionCard>

          {/* K线详情（选中合约后展示，宽度齐平卡片） */}
          {selected && (
            <FuturesDetail quote={selected} onClose={() => setSelected(null)} />
          )}
        </>
      )}
    </AppPage>
  );
};

export default FuturesPage;
