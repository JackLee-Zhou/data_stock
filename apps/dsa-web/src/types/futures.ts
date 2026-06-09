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
}

export interface FuturesListResponse {
  items: FuturesQuote[];
  total: number;
  updatedAt: string;
}
