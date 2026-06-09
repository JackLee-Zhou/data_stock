import React, { useCallback, useEffect, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { futuresApi } from '../api/futures';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { AppPage, PageHeader, SectionCard, Loading, EmptyState, InlineAlert } from '../components/common';
import { FuturesTable } from '../components/futures/FuturesTable';
import type { FuturesQuote } from '../types/futures';

const FuturesPage: React.FC = () => {
  const { t } = useUiLanguage();
  const [items, setItems] = useState<FuturesQuote[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);

  const fetchQuotes = useCallback(async () => {
    let active = true;
    setLoading(true);
    setError(null);
    try {
      const data = await futuresApi.getQuotes();
      if (active) {
        setItems(data.items);
        setUpdatedAt(data.updatedAt);
      }
    } catch (err) {
      if (active) {
        setError(getParsedApiError(err));
      }
    } finally {
      if (active) setLoading(false);
    }
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const cleanup = fetchQuotes();
    return () => { void cleanup.then((fn) => fn?.()); };
  }, [fetchQuotes]);

  useEffect(() => {
    document.title = `${t('layout.nav.futures')} — DSA`;
  }, [t]);

  const formatTime = (isoStr: string): string => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('zh-CN', { hour12: false });
    } catch {
      return isoStr;
    }
  };

  return (
    <AppPage className="space-y-5">
      <PageHeader
        title={t('layout.nav.futures')}
        description="国内商品期货主力合约实时行情"
      />

      {loading && <Loading label="加载期货行情…" />}

      {!loading && error && (
        <SectionCard title="行情加载失败">
          <InlineAlert
            variant="danger"
            title={error.title || '加载失败'}
            message={error.message}
            action={<button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => { void fetchQuotes(); }}>重试</button>}
          />
        </SectionCard>
      )}

      {!loading && !error && items.length === 0 && (
        <SectionCard title="暂无数据">
          <EmptyState
            icon={<TrendingUp className="h-10 w-10" />}
            title="暂无期货行情"
            description="当前没有可用的期货行情数据，请稍后刷新重试。"
            action={<button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => { void fetchQuotes(); }}>刷新</button>}
          />
        </SectionCard>
      )}

      {!loading && !error && items.length > 0 && (
        <SectionCard
          title={`主力合约 (${items.length})`}
          subtitle={updatedAt ? `更新时间: ${formatTime(updatedAt)}` : undefined}
        >
          <FuturesTable items={items} />
        </SectionCard>
      )}
    </AppPage>
  );
};

export default FuturesPage;
