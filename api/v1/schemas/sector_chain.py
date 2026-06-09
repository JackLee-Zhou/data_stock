# -*- coding: utf-8 -*-
"""
板块产业链分析 Schema
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class AvailableSector(BaseModel):
    """可选板块信息"""
    name: str = Field(..., description="板块名称")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")


class AvailableSectorsResponse(BaseModel):
    """可选板块列表"""
    sectors: List[AvailableSector]
    total: int


class ChainStock(BaseModel):
    """产业链节点中的股票"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")


class ChainNode(BaseModel):
    """产业链节点"""
    id: str = Field(..., description="节点唯一标识")
    name: str = Field(..., description="节点/环节名称")
    type: Literal["upstream", "midstream", "downstream"] = Field(..., description="节点类型")
    description: Optional[str] = Field(None, description="环节描述")
    stocks: List[ChainStock] = Field(default_factory=list, description="代表性股票")


class ChainEdge(BaseModel):
    """产业链边/关系"""
    source: str = Field(..., description="源节点 id")
    target: str = Field(..., description="目标节点 id")
    label: Optional[str] = Field(None, description="关系标签")


class BottleneckInfo(BaseModel):
    """卡脖子环节"""
    node_id: str = Field(..., description="对应节点 id")
    description: str = Field(..., description="卡脖子说明")
    severity: Literal["high", "medium", "low"] = Field("medium", description="严重程度")


class HeatNode(BaseModel):
    """热度分析节点"""
    node_id: str = Field(..., description="对应节点 id")
    heat_score: float = Field(..., ge=0, le=100, description="热度评分 0-100")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")
    momentum: Literal["up", "down", "stable"] = Field("stable", description="动量方向")


class HeatAnalysis(BaseModel):
    """热度分析"""
    nodes: List[HeatNode] = Field(default_factory=list)


class SectorChainResponse(BaseModel):
    """产业链分析完整响应"""
    sector_name: str = Field(..., description="板块名称")
    chain_nodes: List[ChainNode] = Field(..., description="产业链节点")
    edges: List[ChainEdge] = Field(default_factory=list, description="节点关系")
    bottlenecks: List[BottleneckInfo] = Field(default_factory=list, description="卡脖子环节")
    heat_analysis: HeatAnalysis = Field(default_factory=HeatAnalysis, description="热度分析")
    generated_at: str = Field(..., description="生成时间(ISO 8601)")
    analysis_time_ms: Optional[int] = Field(None, description="分析耗时(ms)")
