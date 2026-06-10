import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { X } from 'lucide-react';
import type { FuturesQuote } from '../../types/futures';
import { futuresApi } from '../../api/futures';
import { Loading } from '../common';

interface Props {
  quote: FuturesQuote;
  onClose: () => void;
}

export const FuturesDetail: React.FC<Props> = ({ quote, onClose }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chart = useRef<any>(null);
  const [kline, setKline] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    futuresApi.getKline(quote.contractCode, 120).then(data => {
      const items = data.klines.map((k: any) => ({
        time: (k.tradeDate || '').slice(0, 10),
        open: k.open, high: k.high, low: k.low, close: k.close,
      }));
      setKline(items);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [quote.contractCode]);

  useEffect(() => {
    if (!chartRef.current || kline.length === 0) return;
    const c = createChart(chartRef.current, {
      height: 400,
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#9ca3af' },
      grid: { vertLines: { color: '#1f2937' }, horzLines: { color: '#1f2937' } },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: '#374151' },
      timeScale: { borderColor: '#374151', timeVisible: true },
    });
    const candle = (c as any).addCandlestickSeries({
      upColor: '#10b981', downColor: '#ef4444', borderUpColor: '#10b981', borderDownColor: '#ef4444',
      wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });
    candle.setData(kline as any);
    c.timeScale().fitContent();
    chart.current = c;
    return () => { c.remove(); chart.current = null; };
  }, [kline]);

  return (
    <div className="rounded-xl border border-border bg-surface p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-semibold text-foreground">{quote.contractName}</span>
          <span className="text-xs text-secondary-text ml-2">{quote.contractCode}</span>
        </div>
        <button onClick={onClose} className="text-secondary-text hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center">
        {[['最新价', quote.lastPrice?.toFixed(2)], ['涨跌幅', `${(quote.changePct > 0 ? '+' : '')}${quote.changePct?.toFixed(2)}%`], ['成交量', quote.volume?.toLocaleString()], ['持仓量', quote.openInterest?.toLocaleString()]].map(([l, v]) => (
          <div key={l} className="rounded-lg bg-surface-hover p-2">
            <div className="text-[10px] text-tertiary-text">{l}</div>
            <div className={`text-sm font-semibold ${l === '涨跌幅' ? (quote.changePct >= 0 ? 'text-emerald-500' : 'text-red-500') : ''}`}>{v}</div>
          </div>
        ))}
      </div>
      {loading ? <Loading label="K线加载中…" /> : <div ref={chartRef} />}
    </div>
  );
};
