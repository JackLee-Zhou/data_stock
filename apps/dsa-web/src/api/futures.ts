import apiClient from './index';
import { toCamelCase } from './utils';
import type { FuturesListResponse } from '../types/futures';

export const futuresApi = {
  async getQuotes(): Promise<FuturesListResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/futures/quotes');
    return toCamelCase<FuturesListResponse>(response.data);
  },
};
