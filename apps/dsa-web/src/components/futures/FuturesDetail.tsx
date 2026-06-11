import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import { X } from 'lucide-react';
import type { FuturesQuote } from '../../types/futures';
import { futuresApi } from '../../api/futures';
import { Loading } from '../common';

type Timeframe = '1m' | '5m' | '15m' | '1d';

interface DepthLevel { bp: number | null; bv: number; ap: number | null; av: number; }

export const FuturesDetail: React.FC<{ quote: FuturesQuote; onClose: () => void }> = ({ quote, onClose }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [kline, setKline] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tf, setTf] = useState<Timeframe>('1d');
  const [spot, setSpot] = useState({ price: 0, changePct: 0, vol: 0, oi: 0, high: 0, low: 0, open: 0, prevClose: 0 });
  const [depth, setDepth] = useState<DepthLevel[]>([]);

  useEffect(() => {
    setLoading(true);
    futuresApi.getKline(quote.contractCode, 120, tf === '1d' ? 'daily' : tf).then(data => {
      const items = data.klines.map((k: any) => ({
        time: (k.tradeDate || '').slice(0, tf === '1d' ? 10 : 19),  // 日K:date, 分时:datetime
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

  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('/api/v1/ctp/quotes');
        const d = await r.json();
        const q = d.quotes?.[quote.contractCode];
        if (q && q.price > 0) {
          setSpot(s => ({
            price: q.price,
            changePct: s.price > 0 ? ((q.price - s.price) / s.price * 100) : 0,
            vol: Number(q.volume || 0), oi: Number(q.open_interest || 0),
            high: Number(q.high || 0), low: Number(q.low || 0),
            open: Number(q.open || 0), prevClose: Number(q.prev_close || 0),
          }));
          if (q.depth?.length) setDepth(q.depth);
        }
      } catch {}
    };
    poll();
    const t = setInterval(poll, 2000);
    return () => clearInterval(t);
  }, [quote.contractCode]);

  useEffect(() => {
    if (!chartRef.current || kline.length === 0) return;
    const c = createChart(chartRef.current, {
      height: 480,
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

  const chgColor = spot.changePct >= 0 ? 'text-emerald-500' : spot.changePct < 0 ? 'text-red-500' : '';
  const bidMaxVol = Math.max(...depth.map(d => d.bv), 1);
  const askMaxVol = Math.max(...depth.map(d => d.av), 1);
  const fmtN = (v: number) => v > 0 ? (v > 10000 ? (v/10000).toFixed(1)+'万' : v.toLocaleString()) : '-';

  // 过滤无效档位（价格为null的）
  const activeDepth = depth.filter(d => d.bp !== null || d.ap !== null);

  return (
    <div className="glass-panel-lg p-5 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-foreground">{quote.contractName}</span>
          <span className="text-sm text-secondary-text">{quote.contractCode}</span>
          {spot.price > 0 && (
            <>
              <span className={`text-xl font-mono font-bold tabular-nums ${chgColor}`}>{spot.price.toFixed(2)}</span>
              <span className={`text-sm font-medium tabular-nums ${chgColor}`}>
                {spot.changePct >= 0 ? '+' : ''}{Math.abs(spot.changePct).toFixed(2)}%
              </span>
            </>
          )}
          <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-500">CTP实时</span>
        </div>
        <div className="flex items-center gap-1">
          {(['1m', '5m', '15m', '1d'] as Timeframe[]).map(t => (
            <button key={t} onClick={() => setTf(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${tf === t ? 'bg-accent text-white' : 'bg-surface-hover text-secondary-text hover:text-foreground'}`}>
              {t === '1d' ? '日K' : t === '1m' ? '1分' : t === '5m' ? '5分' : '15分'}
            </button>
          ))}
          <button onClick={onClose} className="ml-2 rounded-lg p-1.5 text-secondary-text hover:bg-surface-hover hover:text-foreground"><X className="h-4 w-4" /></button>
        </div>
      </div>

      <div className="flex gap-4">
        {/* Left: Chart */}
        <div className="flex-1 min-w-0">
          <div className="grid grid-cols-6 gap-2 mb-3">
            {[
              ['今开', spot.open], ['最高', spot.high], ['最低', spot.low],
              ['昨收', spot.prevClose], ['成交量', spot.vol], ['持仓', spot.oi],
            ].map(([l, v]) => (
              <div key={l} className="rounded-lg bg-surface-hover px-2 py-1.5 text-center">
                <div className="text-[10px] text-tertiary-text">{l}</div>
                <div className="text-xs font-semibold tabular-nums text-foreground">{fmtN(Number(v))}</div>
              </div>
            ))}
          </div>
          {loading ? <Loading /> : kline.length === 0 ? (
            <div className="flex items-center justify-center h-[400px] rounded-xl bg-surface-hover text-sm text-secondary-text">暂无K线数据</div>
          ) : <div ref={chartRef} />}
        </div>

        {/* Right: 五档盘口 */}
        <div className="w-[240px] shrink-0 space-y-2">
          <div className="text-xs font-medium text-secondary-text mb-2">五档盘口</div>
          {/* Sells (reversed: 卖5→卖1) */}
          {[...activeDepth].reverse().map((d, i) => (
            <div key={`a-${i}`} className="grid grid-cols-[1fr_60px_auto] gap-2 text-xs items-center">
              <span className="text-right text-red-500 font-mono tabular-nums">{d.ap?.toFixed(2) || ''}</span>
              <span className="text-right text-secondary-text tabular-nums">{d.av > 0 ? d.av.toLocaleString() : ''}</span>
              <div className="h-4 rounded-sm bg-red-500/15 relative overflow-hidden">
                <div className="absolute right-0 top-0 h-full bg-red-500/20" style={{ width: `${d.av / askMaxVol * 100}%` }} />
              </div>
            </div>
          ))}
          {/* Spread */}
          <div className="py-1.5 text-center border-y border-border">
            <span className="text-sm font-bold font-mono tabular-nums text-foreground">{spot.price > 0 ? spot.price.toFixed(2) : '-'}</span>
            {activeDepth[0]?.bp && activeDepth[0]?.ap && (
              <span className="text-[10px] text-tertiary-text ml-2">
                价差 {(activeDepth[0].ap! - activeDepth[0].bp!).toFixed(2)}
              </span>
            )}
          </div>
          {/* Buys (买1→买5) */}
          {activeDepth.map((d, i) => (
            <div key={`b-${i}`} className="grid grid-cols-[auto_60px_1fr] gap-2 text-xs items-center">
              <div className="h-4 rounded-sm bg-emerald-500/15 relative overflow-hidden">
                <div className="absolute right-0 top-0 h-full bg-emerald-500/20" style={{ width: `${d.bv / bidMaxVol * 100}%` }} />
              </div>
              <span className="text-left text-secondary-text tabular-nums">{d.bv > 0 ? d.bv.toLocaleString() : ''}</span>
              <span className="text-left text-emerald-500 font-mono tabular-nums">{d.bp?.toFixed(2) || ''}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
