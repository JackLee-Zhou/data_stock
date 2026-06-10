import React, { useCallback, useEffect, useState } from 'react';
import { LineChart } from 'lucide-react';
import { shadowAccountApi, type ShadowAccount, type ShadowPosition, type ShadowTrade } from '../api/shadowAccount';
import { AppPage, PageHeader, SectionCard, Loading, EmptyState, InlineAlert, Button } from '../components/common';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const ShadowAccountPage: React.FC = () => {
  const { t } = useUiLanguage();
  const [account, setAccount] = useState<ShadowAccount | null>(null);
  const [positions, setPositions] = useState<ShadowPosition[]>([]);
  const [history, setHistory] = useState<ShadowTrade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tradeForm, setTradeForm] = useState({ symbol: '', side: 'buy', quantity: 100, price: 0 });

  const fetchAll = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [acct, pos, hist] = await Promise.all([
        shadowAccountApi.getAccount(),
        shadowAccountApi.getPositions(),
        shadowAccountApi.getHistory(20),
      ]);
      setAccount(acct); setPositions(pos); setHistory(hist);
    } catch (e: any) { setError(e?.message || '加载失败'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);
  useEffect(() => { document.title = `${t('layout.nav.shadowAccount')} — DSA`; }, [t]);

  const [fetchingPrice, setFetchingPrice] = useState(false);
  const handleSymbolBlur = async () => {
    const sym = tradeForm.symbol.trim();
    if (!sym || sym.length < 4) return;
    setFetchingPrice(true);
    try {
      const r = await fetch(`/api/v1/stocks/${sym.toUpperCase()}/quote`);
      if (r.ok) {
        const data = await r.json();
        if (data.price) setTradeForm(f => ({ ...f, symbol: sym.toUpperCase(), price: data.price }));
      }
    } catch {}
    finally { setFetchingPrice(false); }
  };

  const handleTrade = async () => {
    if (!tradeForm.symbol || tradeForm.price <= 0) return;
    try {
      await shadowAccountApi.placeTrade(tradeForm.symbol.toUpperCase(), tradeForm.side, tradeForm.quantity, tradeForm.price);
      setTradeForm({ symbol: '', side: 'buy', quantity: 100, price: 0 });
      await fetchAll();
    } catch (e: any) { setError(e?.message || '交易失败'); }
  };

  if (loading) return <AppPage className="space-y-5"><PageHeader title={t('layout.nav.shadowAccount')} /><Loading /></AppPage>;
  if (error) return <AppPage className="space-y-5"><PageHeader title={t('layout.nav.shadowAccount')} /><InlineAlert variant="danger" title="加载失败" message={error} action={<button onClick={fetchAll}>重试</button>} /></AppPage>;

  return (
    <AppPage className="space-y-5">
      <PageHeader title={t('layout.nav.shadowAccount')} description="模拟交易账户，初始资金100万，可用于验证分析策略" />

      {/* 账户概览 */}
      {account && (
        <SectionCard title="账户概览">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ['余额', `¥${account.balance.toLocaleString()}`],
              ['买入总额', `¥${account.totalCost.toLocaleString()}`],
              ['卖出总额', `¥${account.totalSold.toLocaleString()}`],
              ['已实现盈亏', `${account.realizedPnl >= 0 ? '+' : ''}¥${account.realizedPnl.toLocaleString()}`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-border p-4">
                <div className="text-xs text-secondary-text">{label}</div>
                <div className={`mt-1 text-lg font-semibold ${label === '已实现盈亏' ? (account.realizedPnl >= 0 ? 'text-emerald-600' : 'text-red-500') : ''}`}>{value}</div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* 下单 */}
      <SectionCard title="模拟交易">
        <div className="flex flex-wrap items-end gap-3">
          <div><label className="text-xs text-secondary-text">代码</label><input className="w-24 rounded-lg border border-border bg-surface px-3 py-2 text-sm" value={tradeForm.symbol} onChange={e => setTradeForm({ ...tradeForm, symbol: e.target.value })} onBlur={handleSymbolBlur} placeholder="600519" /></div>
          <div><label className="text-xs text-secondary-text">方向</label><select className="rounded-lg border border-border bg-surface px-3 py-2 text-sm" value={tradeForm.side} onChange={e => setTradeForm({ ...tradeForm, side: e.target.value })}><option value="buy">买入</option><option value="sell">卖出</option></select></div>
          <div><label className="text-xs text-secondary-text">数量</label><input type="number" className="w-24 rounded-lg border border-border bg-surface px-3 py-2 text-sm" value={tradeForm.quantity} onChange={e => setTradeForm({ ...tradeForm, quantity: +e.target.value })} /></div>
          <div><label className="text-xs text-secondary-text">价格 {fetchingPrice && '⏳'}</label><input type="number" className="w-28 rounded-lg border border-border bg-surface px-3 py-2 text-sm" value={tradeForm.price || ''} onChange={e => setTradeForm({ ...tradeForm, price: +e.target.value })} placeholder={fetchingPrice ? "获取中..." : "自动/手动"} /></div>
          <Button variant="primary" size="md" onClick={handleTrade} disabled={!tradeForm.symbol || tradeForm.price <= 0}>{tradeForm.side === 'buy' ? '买入' : '卖出'}</Button>
        </div>
      </SectionCard>

      {/* 持仓 */}
      <SectionCard title={`持仓 (${positions.length})`}>
        {positions.length === 0 ? <EmptyState icon={<LineChart className="h-8 w-8" />} title="暂无持仓" description="在上方输入股票代码和价格进行模拟交易" /> : (
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-border"><th className="px-3 py-2 text-left text-xs">代码</th><th className="px-3 py-2 text-right text-xs">数量</th><th className="px-3 py-2 text-right text-xs">均价</th><th className="px-3 py-2 text-right text-xs">成本</th></tr></thead><tbody className="divide-y divide-border">
            {positions.map(p => (
              <tr key={p.symbol} className="hover:bg-surface-hover"><td className="px-3 py-2 font-medium">{p.symbol}</td><td className="px-3 py-2 text-right">{p.quantity}</td><td className="px-3 py-2 text-right">¥{p.avgCost.toFixed(2)}</td><td className="px-3 py-2 text-right">¥{p.totalCost.toLocaleString()}</td></tr>
            ))}
          </tbody></table></div>
        )}
      </SectionCard>

      {/* 历史 */}
      <SectionCard title={`交易记录 (${history.length})`}>
        {history.length === 0 ? <EmptyState icon={<LineChart className="h-8 w-8" />} title="暂无记录" /> : (
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-border"><th className="px-3 py-2 text-left text-xs">时间</th><th className="px-3 py-2 text-left text-xs">代码</th><th className="px-3 py-2 text-left text-xs">方向</th><th className="px-3 py-2 text-right text-xs">数量</th><th className="px-3 py-2 text-right text-xs">价格</th></tr></thead><tbody className="divide-y divide-border">
            {history.map(t => (
              <tr key={t.id} className="hover:bg-surface-hover"><td className="px-3 py-2 text-secondary-text">{t.date}</td><td className="px-3 py-2 font-medium">{t.symbol}</td><td className={`px-3 py-2 ${t.side === 'buy' ? 'text-emerald-600' : 'text-red-500'}`}>{t.side === 'buy' ? '买入' : '卖出'}</td><td className="px-3 py-2 text-right">{t.quantity}</td><td className="px-3 py-2 text-right">¥{t.price.toFixed(2)}</td></tr>
            ))}
          </tbody></table></div>
        )}
      </SectionCard>
    </AppPage>
  );
};

export default ShadowAccountPage;
