import React, { useCallback, useEffect, useMemo } from 'react';
import { GitBranch } from 'lucide-react';
import { useSectorChainStore } from '../stores/sectorChainStore';
import { useUiLanguage } from '../contexts/UiLanguageContext';
import { AppPage, PageHeader, SectionCard, Loading, EmptyState, InlineAlert } from '../components/common';
import { SectorSearchSelect } from '../components/sectorChain/SectorSearchSelect';
import { SupplyChainGraph } from '../components/sectorChain/SupplyChainGraph';
import { BottleneckCards } from '../components/sectorChain/BottleneckCards';
import { ChainHeatmap } from '../components/sectorChain/ChainHeatmap';
// No extra type imports needed here

const SectorChainPage: React.FC = () => {
  const { t } = useUiLanguage();
  const {
    availableSectors,
    sectorsLoading,
    selectedSector,
    chainResult,
    isLoading,
    error,
    analyzeSector,
  } = useSectorChainStore();

  // 只在挂载时加载一次板块列表（避免 fetchSectors 引用变化导致无限循环）
  useEffect(() => {
    void useSectorChainStore.getState().fetchSectors();
  }, []);

  useEffect(() => {
    document.title = `${t('layout.nav.sectorChain')} — DSA`;
  }, [t]);

  const nodeNameMap = useMemo(() => {
    const map = new Map<string, string>();
    if (chainResult?.chainNodes) {
      for (const n of chainResult.chainNodes) {
        map.set(n.id, n.name);
      }
    }
    return map;
  }, [chainResult]);

  const bottleneckNodeIds = useMemo(() => {
    const set = new Set<string>();
    if (chainResult?.bottlenecks) {
      for (const b of chainResult.bottlenecks) {
        set.add(b.nodeId);
      }
    }
    return set;
  }, [chainResult]);

  const handleAnalyze = useCallback((name: string) => {
    void analyzeSector(name);
  }, [analyzeSector]);

  const getNodeName = useCallback((id: string) => nodeNameMap.get(id) || id, [nodeNameMap]);

  const formatTime = (isoStr: string): string => {
    try {
      return new Date(isoStr).toLocaleString('zh-CN', { hour12: false });
    } catch {
      return isoStr;
    }
  };

  return (
    <AppPage className="space-y-5">
      <PageHeader
        title={t('layout.nav.sectorChain')}
        description="输入行业板块名称，AI 自动分析产业链上下游关系、卡脖子环节与各环节市场热度"
      />

      {/* Search & Select */}
      <SectionCard title="选择板块">
        <SectorSearchSelect
          sectors={availableSectors}
          loading={sectorsLoading}
          disabled={isLoading}
          onAnalyze={handleAnalyze}
        />
      </SectionCard>

      {/* Loading */}
      {isLoading && (
        <SectionCard title="分析中">
          <Loading label={`正在分析「${selectedSector}」产业链结构，AI 思考中…`} />
        </SectionCard>
      )}

      {/* Error */}
      {!isLoading && error && (
        <SectionCard title="分析失败">
          <InlineAlert
            variant="danger"
            title={error.title || '分析失败'}
            message={error.message}
            action={<button type="button" className="text-sm font-medium text-accent hover:underline" onClick={() => selectedSector && handleAnalyze(selectedSector)}>重试</button>}
          />
          {error.suggestions && error.suggestions.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-secondary-text">试试：</span>
              {error.suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="rounded-full border border-border px-3 py-1 text-xs text-accent hover:bg-accent/10 transition-colors"
                  onClick={() => handleAnalyze(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </SectionCard>
      )}

      {/* Empty (no analysis yet) */}
      {!isLoading && !error && !chainResult && (
        <SectionCard title="产业链图谱">
          <EmptyState
            icon={<GitBranch className="h-10 w-10" />}
            title="选择板块开始分析"
            description={'输入板块名称（如「半导体」、「新能源车」、「光伏」），系统将自动分析该行业的产业链结构。'}
          />
        </SectionCard>
      )}

      {/* Results */}
      {!isLoading && !error && chainResult && (
        <>
          {/* Topology Graph */}
          <SectionCard
            title="产业链拓扑图"
            subtitle={chainResult.sectorName}
            actions={
              chainResult.analysisTimeMs ? (
                <span className="text-xs text-tertiary-text">
                  {formatTime(chainResult.generatedAt)} · {(chainResult.analysisTimeMs / 1000).toFixed(1)}s
                </span>
              ) : undefined
            }
          >
            <SupplyChainGraph
              nodes={chainResult.chainNodes}
              edges={chainResult.edges}
              bottleneckNodeIds={bottleneckNodeIds}
            />
          </SectionCard>

          {/* Bottlenecks */}
          <SectionCard title="卡脖子环节">
            <BottleneckCards
              bottlenecks={chainResult.bottlenecks}
              getNodeName={getNodeName}
            />
          </SectionCard>

          {/* Heatmap */}
          <SectionCard title="各环节热度">
            <ChainHeatmap
              nodes={chainResult.heatAnalysis.nodes}
              getNodeName={getNodeName}
            />
          </SectionCard>
        </>
      )}
    </AppPage>
  );
};

export default SectorChainPage;
