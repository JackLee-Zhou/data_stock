export interface AvailableSector {
  name: string;
  changePct?: number;
}

export interface AvailableSectorsResponse {
  sectors: AvailableSector[];
  total: number;
}

export interface ChainStock {
  code: string;
  name: string;
}

export interface ChainNode {
  id: string;
  name: string;
  type: 'upstream' | 'midstream' | 'downstream';
  description?: string;
  stocks: ChainStock[];
}

export interface ChainEdge {
  source: string;
  target: string;
  label?: string;
}

export interface BottleneckInfo {
  nodeId: string;
  description: string;
  severity: 'high' | 'medium' | 'low';
}

export interface HeatNode {
  nodeId: string;
  heatScore: number;
  changePct?: number;
  momentum: 'up' | 'down' | 'stable';
  source?: 'market' | 'ai';
  sourceLabel?: string;
}

export interface HeatAnalysis {
  nodes: HeatNode[];
}

export interface SectorChainResponse {
  sectorName: string;
  chainNodes: ChainNode[];
  edges: ChainEdge[];
  bottlenecks: BottleneckInfo[];
  heatAnalysis: HeatAnalysis;
  generatedAt: string;
  analysisTimeMs?: number;
  fromCache?: boolean;
  cachedAt?: string;
}
