import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import { X } from 'lucide-react';
import type { FuturesQuote } from '../../types/futures';
import { futuresApi } from '../../api/futures';
import { Loading } from '../common';

export const FuturesDetail: React.FC<{ quote: FuturesQuote; onClose: () => void }> = ({ quote, onClose }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [kline, setKline] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [spot, setSpot] = useState({ price: 0, changePct: 0, vol: 0, oi: 0, high: 0, low: 0, open: 0, bid1: 0, ask1: 0, bidVol1: 0, askVol1: 0 });

  // 拉K线
  useEffect(() => {
    setLoading(true);
    futuresApi.getKline(quote.contractCode, 120).then(data => {
      const items = data.klines.map((k: any) => ({
        time: (k.tradeDate || '').slice(0, 10),
        open: k.open, high: k.high, low: k.low, close: k.close,
      }));
      setKline(items);
      if (items.length >= 2) {
        const last = items[items.length - 1], prev = items[items.length - 2];
        setSpot(s => ({ ...s, price: last.close, changePct: prev.close ? (last.close - prev.close) / prev.close * 100 : 0 }));
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [quote.contractCode]);

  // 轮询 CTP 实时行情（每3秒）
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('/api/v1/ctp/quotes');
        const d = await r.json();
        const q = d.quotes?.[quote.contractCode];
        if (q && q.price > 0) {
          const prev = spot.price || q.price;
          setSpot({
            price: q.price,
            changePct: prev ? ((q.price - prev) / prev * 100) : 0,
            vol: q.volume || 0,
            oi: q.open_interest || 0,
            high: q.high || 0,
            low: q.low || 0,
            open: q.open || 0,
            bid1: q.bid1 || 0,
            ask1: q.ask1 || 0,
            bidVol1: q.bid_vol1 || 0,
            askVol1: q.ask_vol1 || 0,
          });
        }
      } catch {}
    };
    poll();
    const timer = setInterval(poll, 3000);
    return () => clearInterval(timer);
  }, [quote.contractCode]);

  // K线图
  useEffect(() => {
    if (!chartRef.current || kline.length === 0) return;
    const c = createChart(chartRef.current, {
      height: 550,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151', timeVisible: true },
    });
    const candle = c.addSeries(CandlestickSeries, {
      upColor: '#10b981', downColor: '#ef4444',
      borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });
    candle.setData(kline);
    c.timeScale().fitContent();
    return () => { c.remove(); };
  }, [kline]);

  const fmt = (v: number) => v > 0 ? v.toLocaleString() : '-';

  return (
    <div className="glass-panel-lg p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-lg font-semibold text-foreground">{quote.contractName}</span>
          <span className="text-sm text-secondary-text ml-2">{quote.contractCode}</span>
          <span className="inline-flex items-center ml-3 px-2 py-0.5 rounded-full text-[11px] bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
            ● CTP 实时
          </span>
        </div>
        <button onClick={onClose} className="rounded-lg p-1.5 text-secondary-text hover:bg-surface-hover hover:text-foreground transition-colors"><X className="h-5 w-5" /></button>
      </div>

      {/* 实时行情卡片 - 买一卖一 + 盘口量 */}
      <div className="grid grid-cols-5 gap-3">
        {[
          ['最新价', spot.price > 0 ? spot.price.toFixed(2) : '-', spot.changePct >= 0 ? 'text-emerald-500' : 'text-red-500'],
          ['涨跌幅', spot.price > 0 ? `${spot.changePct >= 0 ? '+' : ''}${spot.changePct.toFixed(2)}%` : '-', spot.changePct >= 0 ? 'text-emerald-500' : 'text-red-500'],
          ['今开', spot.open > 0 ? spot.open.toFixed(2) : '-', ''],
          ['最高', spot.high > 0 ? spot.high.toFixed(2) : '-', 'text-emerald-500'],
          ['最低', spot.low > 0 ? spot.low.toFixed(2) : '-', 'text-red-500'],
        ].map(([l, v, cls]) => (
          <div key={l} className="rounded-xl bg-surface-hover p-3 text-center">
            <div className="text-[11px] text-tertiary-text mb-1">{l}</div>
            <div className={`text-base font-bold tabular-nums ${cls}`}>{v}</div>
          </div>
        ))}
      </div>

      {/* 买卖盘口 */}
      <div className="grid grid-cols-4 gap-3">
        {[
          ['买一价', spot.bid1 > 0 ? spot.bid1.toFixed(2) : '-', 'text-emerald-500'],
          ['买一量', spot.bidVol1 > 0 ? fmt(spot.bidVol1) : '-', ''],
          ['卖一价', spot.ask1 > 0 ? spot.ask1.toFixed(2) : '-', 'text-red-500'],
          ['卖一量', spot.askVol1 > 0 ? fmt(spot.askVol1) : '-', ''],
        ].map(([l, v, cls]) => (
          <div key={l} className="rounded-xl bg-surface-hover p-3 text-center">
            <div className="text-[11px] text-tertiary-text mb-1">{l}</div>
            <div className={`text-sm font-bold tabular-nums ${cls}`}>{v}</div>
          </div>
        ))}
      </div>

      {/* 成交量+持仓 */}
      <div className="grid grid-cols-3 gap-3">
        {[
          ['成交量', fmt(spot.vol)],
          ['持仓量', fmt(spot.oi)],
          ['昨收', quote.prevClose ? quote.prevClose.toFixed(2) : '-'],
        ].map(([l, v]) => (
          <div key={l} className="rounded-xl bg-surface-hover p-3 text-center">
            <div className="text-[11px] text-tertiary-text mb-1">{l}</div>
            <div className="text-sm font-semibold tabular-nums text-foreground">{v}</div>
          </div>
        ))}
      </div>

      {/* K线 */}
      {loading ? <Loading label="K线加载中…" /> : kline.length === 0 ? (
        <div className="flex items-center justify-center h-[500px] rounded-xl bg-surface-hover text-sm text-secondary-text">该合约暂无K线数据</div>
      ) : <div ref={chartRef} className="w-full" />}
    </div>
  );
};
