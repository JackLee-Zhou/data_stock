import apiClient from './index';
import { toCamelCase } from './utils';
import type { AvailableSectorsResponse, SectorChainResponse } from '../types/sectorChain';

export const sectorChainApi = {
  async listSectors(): Promise<AvailableSectorsResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/sector-chain/sectors');
    return toCamelCase<AvailableSectorsResponse>(response.data);
  },

  async getChain(sectorName: string): Promise<SectorChainResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/sector-chain/chain/${encodeURIComponent(sectorName)}`,
      { timeout: 120000 },
    );
    return toCamelCase<SectorChainResponse>(response.data);
  },
};
