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
  const [spot, setSpot] = useState({ price: 0, changePct: 0, vol: 0, oi: 0 });

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
        setSpot({ price: last.close, changePct: prev.close ? (last.close - prev.close) / prev.close * 100 : 0, vol: 0, oi: 0 });
      } else if (items.length === 1) {
        setSpot({ price: items[0].close, changePct: 0, vol: 0, oi: 0 });
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [quote.contractCode]);

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

  return (
    <div className="glass-panel-lg p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-lg font-semibold text-foreground">{quote.contractName}</span>
          <span className="text-sm text-secondary-text ml-2">{quote.contractCode}</span>
        </div>
        <button onClick={onClose} className="rounded-lg p-1.5 text-secondary-text hover:bg-surface-hover hover:text-foreground transition-colors">
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Price cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          ['最新价', spot.price > 0 ? spot.price.toFixed(2) : '-'],
          ['涨跌幅', spot.price > 0 ? `${spot.changePct >= 0 ? '+' : ''}${spot.changePct.toFixed(2)}%` : '-'],
          ['成交量', quote.volume > 0 ? quote.volume.toLocaleString() : '-'],
          ['持仓量', quote.openInterest > 0 ? quote.openInterest.toLocaleString() : '-'],
        ].map(([l, v]) => (
          <div key={l} className="rounded-xl bg-surface-hover p-3 text-center">
            <div className="text-[11px] text-tertiary-text mb-1">{l}</div>
            <div className={`text-base font-bold tabular-nums ${l === '涨跌幅' ? (spot.changePct >= 0 ? 'text-emerald-500' : 'text-red-500') : 'text-foreground'}`}>{v}</div>
          </div>
        ))}
      </div>

      {/* K-line chart - larger */}
      {loading ? (
        <Loading label="K线加载中…" />
      ) : kline.length === 0 ? (
        <div className="flex items-center justify-center h-[500px] rounded-xl bg-surface-hover text-sm text-secondary-text">
          该合约暂无K线数据
        </div>
      ) : (
        <div ref={chartRef} className="w-full" />
      )}
    </div>
  );
};
