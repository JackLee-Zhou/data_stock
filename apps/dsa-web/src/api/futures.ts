import apiClient from './index';
import { toCamelCase } from './utils';
import type { FuturesKlineResponse, FuturesListResponse } from '../types/futures';

export const futuresApi = {
  async getQuotes(market?: string): Promise<FuturesListResponse> {
    const params: any = {};
    if (market) params.market = market;
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/futures/quotes', { params });
    return toCamelCase<FuturesListResponse>(response.data);
  },
  async getKline(code: string, days = 120): Promise<FuturesKlineResponse> {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/futures/quotes/${encodeURIComponent(code)}/kline`, { params: { days }, timeout: 30000 });
    return toCamelCase<FuturesKlineResponse>(response.data);
  },
};
