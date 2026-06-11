import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { ChainNode, ChainEdge as ChainEdgeData } from '../../types/sectorChain';

/* ---------- Custom Node ---------- */
const typeColors: Record<string, string> = {
  upstream: 'border-blue-400 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-500',
  midstream: 'border-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 dark:border-emerald-500',
  downstream: 'border-amber-400 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-500',
};

const typeLabels: Record<string, string> = {
  upstream: '上游',
  midstream: '中游',
  downstream: '下游',
};

interface ChainNodeData extends Record<string, unknown> {
  label: string;
  nodeType: string;
  description: string;
  stockCount: number;
  isBottleneck: boolean;
}

const ChainFlowNode: React.FC<{ data: ChainNodeData }> = ({ data }) => {
  const isBottleneck = data.isBottleneck;
  return (
    <div
      className={`rounded-xl border-2 px-4 py-3 shadow-sm min-w-[140px] max-w-[200px] ${
        typeColors[data.nodeType] || 'border-gray-300 bg-white'
      } ${isBottleneck ? 'animate-pulse border-red-500 shadow-red-200' : ''}`}
      title={data.description}
    >
      <div className="text-xs text-secondary-text mb-1">{typeLabels[data.nodeType] || data.nodeType}</div>
      <div className="font-semibold text-sm text-foreground">{data.label}</div>
      <div className="text-xs text-secondary-text mt-1">
        {data.stockCount > 0 ? `${data.stockCount} 只成分股` : ''}
      </div>
      {isBottleneck && (
        <div className="mt-1 inline-flex items-center rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-600 dark:bg-red-900/30 dark:text-red-400">
          卡脖子
        </div>
      )}
    </div>
  );
};

const nodeTypes = { chainNode: ChainFlowNode };

/* ---------- Props ---------- */
interface SupplyChainGraphProps {
  nodes: ChainNode[];
  edges: ChainEdgeData[];
  bottleneckNodeIds: Set<string>;
}

function layoutNodes(
  rawNodes: ChainNode[],
  rawEdges: ChainEdgeData[],
  bottleneckNodeIds: Set<string>,
): { flowNodes: Node<ChainNodeData>[]; flowEdges: Edge[] } {
  if (rawNodes.length === 0) return { flowNodes: [], flowEdges: [] };

  // Group by type: upstream, midstream, downstream
  const groups: Record<string, ChainNode[]> = { upstream: [], midstream: [], downstream: [] };
  for (const n of rawNodes) {
    const t = n.type || 'midstream';
    if (!groups[t]) groups[t] = [];
    groups[t].push(n);
  }

  const xGap = 220;
  const yGap = 140;
  const startX = 100;
  const typeOrder = ['upstream', 'midstream', 'downstream'];

  const flowNodes: Node<ChainNodeData>[] = [];
  const yOffsets: Record<string, number> = {};

  for (const t of typeOrder) {
    const items = groups[t] || [];
    const totalHeight = items.length * yGap;
    let y = -(totalHeight / 2) + yGap / 2;
    for (const item of items) {
      const colIdx = typeOrder.indexOf(t);
      flowNodes.push({
        id: item.id,
        type: 'chainNode',
        position: { x: startX + colIdx * xGap, y },
        data: {
          label: item.name,
          nodeType: item.type,
          description: item.description || '',
          stockCount: (item.stocks || []).length,
          isBottleneck: bottleneckNodeIds.has(item.id),
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      });
      yOffsets[item.id] = y;
      y += yGap;
    }
  }

  const flowEdges: Edge[] = rawEdges.map((e, i) => ({
    id: `${e.source}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: true,
    style: { stroke: 'var(--text-muted-text)', strokeWidth: 1.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color: 'var(--text-muted-text)' },
  }));

  return { flowNodes, flowEdges };
}

export const SupplyChainGraph: React.FC<SupplyChainGraphProps> = ({
  nodes,
  edges,
  bottleneckNodeIds,
}) => {
  const { flowNodes, flowEdges } = useMemo(
    () => layoutNodes(nodes, edges, bottleneckNodeIds),
    [nodes, edges, bottleneckNodeIds],
  );

  const [rnNodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [rnEdges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  // Re-sync when data changes
  React.useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  if (nodes.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-border bg-surface-hover">
        <p className="text-sm text-secondary-text">暂无产业链数据</p>
      </div>
    );
  }

  return (
    <div className="h-[500px] w-full rounded-xl border border-border bg-surface">
      <ReactFlow
        nodes={rnNodes}
        edges={rnEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.3}
        maxZoom={2}
        attributionPosition="bottom-right"
      >
        <Background color="var(--border-subtle)" gap={20} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const t = (n.data as ChainNodeData | undefined)?.nodeType;
            if (t === 'upstream') return 'var(--color-cyan)';
            if (t === 'midstream') return 'var(--color-success)';
            if (t === 'downstream') return 'var(--color-warning)';
            return 'var(--text-muted-text)';
          }}
          style={{ height: 100 }}
        />
      </ReactFlow>
    </div>
  );
};
