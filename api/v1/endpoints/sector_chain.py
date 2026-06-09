# -*- coding: utf-8 -*-
"""
板块产业链分析接口

GET  /api/v1/sector-chain/sectors          — 列出可选行业板块
GET  /api/v1/sector-chain/chain/{name}     — 分析指定板块的产业链
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.sector_chain import (
    AvailableSector,
    AvailableSectorsResponse,
    SectorChainResponse,
    ChainNode,
    ChainEdge,
    BottleneckInfo,
    HeatNode,
    HeatAnalysis,
)
from src.services.sector_chain_service import SectorChainService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/sectors",
    response_model=AvailableSectorsResponse,
    responses={
        200: {"description": "可选板块列表"},
    },
    summary="列出可选行业板块",
    description="返回当前市场可用的行业板块列表，用于前端下拉选择。按涨跌幅降序排列。",
)
def list_available_sectors() -> AvailableSectorsResponse:
    """列出所有可选的行业板块。"""
    service = SectorChainService()
    sectors_raw = service.list_available_sectors()

    sectors = [AvailableSector(**s) for s in sectors_raw]
    return AvailableSectorsResponse(sectors=sectors, total=len(sectors))


@router.get(
    "/chain/{sector_name:path}",
    response_model=SectorChainResponse,
    responses={
        200: {"description": "产业链分析结果"},
        404: {"description": "未找到该板块的成分股"},
        503: {"description": "LLM 分析失败"},
    },
    summary="分析板块产业链",
    description="输入行业板块名称，返回该板块的产业链结构（上下游节点、关系、卡脖子环节、热度分析）。"
    "结果默认缓存 1 天，传 ?refresh=true 强制重新生成。",
)
def get_sector_chain(
    sector_name: str,
    refresh: bool = Query(False, description="跳过缓存，强制重新生成"),
) -> SectorChainResponse:
    """分析指定板块的产业链结构。"""
    service = SectorChainService()

    try:
        result = service.analyze(sector_name, force_refresh=refresh)
    except RuntimeError as exc:
        logger.error("Sector chain LLM config error for %s: %s", sector_name, exc)
        raise HTTPException(
            status_code=503,
            detail={
                "title": "AI 模型未配置",
                "message": "请先在设置页配置 LLM 模型（如 DeepSeek API Key）。",
                "error_type": "llm_not_configured",
            },
        ) from exc

    if result is None:
        suggestions = service.fuzzy_suggest(sector_name, limit=5)
        hint = ""
        if suggestions:
            hint = "。试试：" + "、".join(suggestions)
        raise HTTPException(
            status_code=404,
            detail={
                "title": "分析失败",
                "message": (
                    f"无法分析「{sector_name}」的产业链。请检查板块名称是否正确，"
                    f"或确认 AI 模型已正确配置{hint}"
                ),
                "error_type": "sector_not_found",
                "suggestions": suggestions,
            },
        )

    return SectorChainResponse(
        sector_name=result.get("sector_name", sector_name),
        chain_nodes=[ChainNode(**n) for n in result.get("chain_nodes", [])],
        edges=[ChainEdge(**e) for e in result.get("edges", [])],
        bottlenecks=[BottleneckInfo(**b) for b in result.get("bottlenecks", [])],
        heat_analysis=_build_heat_analysis(result.get("heat_analysis", {})),
        generated_at=result.get("generated_at", ""),
        analysis_time_ms=result.get("analysis_time_ms"),
    )


def _build_heat_analysis(raw: dict) -> HeatAnalysis:
    """从 LLM 返回的原始 dict 构建 HeatAnalysis。"""
    nodes = raw.get("nodes", []) if isinstance(raw, dict) else []
    return HeatAnalysis(nodes=[HeatNode(**n) for n in nodes])
