import { create } from 'zustand';
import type { AvailableSector, SectorChainResponse } from '../types/sectorChain';
import { sectorChainApi } from '../api/sectorChain';
import { getParsedApiError, type ParsedApiError } from '../api/error';

interface SectorChainState {
  availableSectors: AvailableSector[];
  sectorsLoading: boolean;
  selectedSector: string | null;
  chainResult: SectorChainResponse | null;
  isLoading: boolean;
  error: ParsedApiError | null;

  fetchSectors: () => Promise<void>;
  analyzeSector: (name: string) => Promise<void>;
  reset: () => void;
}

export const useSectorChainStore = create<SectorChainState>((set) => ({
  availableSectors: [],
  sectorsLoading: false,
  selectedSector: null,
  chainResult: null,
  isLoading: false,
  error: null,

  fetchSectors: async () => {
    set({ sectorsLoading: true });
    try {
      const data = await sectorChainApi.listSectors();
      set({ availableSectors: data.sectors, sectorsLoading: false });
    } catch {
      set({ sectorsLoading: false });
    }
  },

  analyzeSector: async (name: string) => {
    set({ selectedSector: name, isLoading: true, error: null, chainResult: null });
    try {
      const result = await sectorChainApi.getChain(name);
      set({ chainResult: result, isLoading: false });
    } catch (err) {
      set({ error: getParsedApiError(err), isLoading: false });
    }
  },

  reset: () => set({
    selectedSector: null,
    chainResult: null,
    error: null,
  }),
}));
