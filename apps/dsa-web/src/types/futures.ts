export interface FuturesQuote {
  contractCode: string;
  contractName: string;
  lastPrice: number;
  change: number;
  changePct: number;
  volume: number;
  openInterest: number;
  high?: number;
  low?: number;
  open?: number;
  prevClose?: number;
  market: string;
}

export interface FuturesListResponse {
  items: FuturesQuote[];
  total: number;
  updatedAt: string;
}

export interface KlineItem {
  tradeDate: string; open: number; high: number; low: number; close: number;
  volume: number; openInterest: number;
}

export interface FuturesKlineResponse {
  code: string;
  klines: KlineItem[];
  fromCache: boolean;
}
