import apiClient from './index';

export interface ShadowAccount {
  id: number; name: string; balance: number;
  totalCost: number; totalSold: number; realizedPnl: number;
}

export interface ShadowPosition {
  symbol: string; quantity: number; avgCost: number; totalCost: number;
}

export interface ShadowTrade {
  id: number; symbol: string; side: string;
  quantity: number; price: number; date: string; note: string;
}

export const shadowAccountApi = {
  async getAccount(): Promise<ShadowAccount> {
    const r = await apiClient.get('/api/v1/portfolio/shadow/account');
    return r.data;
  },
  async getPositions(): Promise<ShadowPosition[]> {
    const r = await apiClient.get('/api/v1/portfolio/shadow/positions');
    return r.data.positions ?? [];
  },
  async getHistory(limit = 20): Promise<ShadowTrade[]> {
    const r = await apiClient.get('/api/v1/portfolio/shadow/history', { params: { limit } });
    return r.data.trades ?? [];
  },
  async placeTrade(symbol: string, side: string, quantity: number, price: number) {
    const r = await apiClient.post('/api/v1/portfolio/shadow/trade', null, {
      params: { symbol, side, quantity, price },
    });
    return r.data;
  },
};
