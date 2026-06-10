import React, { useCallback, useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';
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

  return (
    <AppPage className="space-y-5">
      <CtpStatusBar />
      <PageHeader title={t('layout.nav.futures')} description="国内期货实时行情 · 点击合约查看K线" />

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          ['domestic', '国内期货'],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key as Tab)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${tab === key ? 'bg-accent text-white' : 'bg-surface-hover text-secondary-text hover:text-foreground'}`}
          >
            {label}
          </button>
        ))}
        {updatedAt && <span className="self-center ml-auto text-xs text-tertiary-text">更新: {new Date(updatedAt).toLocaleTimeString('zh-CN')}</span>}
      </div>

      {loading && <Loading label="加载期货行情…" />}
      {!loading && error && <SectionCard title="加载失败"><p className="text-sm text-red-500">{error}</p></SectionCard>}
      {!loading && !error && items.length === 0 && <EmptyState icon={<TrendingUp className="h-10 w-10" />} title="暂无数据" />}
      {!loading && !error && items.length > 0 && (
        <div className="flex gap-4">
          <div className={selected ? 'w-1/2' : 'w-full'}>
            <SectionCard title={`${tab === 'domestic' ? '国内' : '国际'}合约 (${items.length})`}>
              <FuturesTable items={items} onSelect={setSelected} selected={selected?.contractCode} />
            </SectionCard>
          </div>
          {selected && (
            <div className="w-1/2">
              <FuturesDetail quote={selected} onClose={() => setSelected(null)} />
            </div>
          )}
        </div>
      )}
    </AppPage>
  );
};

export default FuturesPage;
