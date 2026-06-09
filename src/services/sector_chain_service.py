# -*- coding: utf-8 -*-
"""
板块产业链分析服务

新架构（减少 akshare 请求）：
1. LLM 直接生成产业链拓扑（利用预训练知识，无需拉取成分股）
2. 拉取一次行业+概念板块排行作为市场热度上下文
3. 后处理：将 LLM 生成的节点与真实板块匹配，填充涨跌幅/热度

相比旧方案，aksare 请求从 O(n) 降到 O(1)，大幅降低被 ban 风险。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from data_provider.base import DataFetcherManager

logger = logging.getLogger(__name__)

TZ_SHANGHAI = timezone(timedelta(hours=8))

# ── Prompt ──────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位资深中国产业链分析师。请直接基于你的知识分析给定行业的产业链结构。

分析维度：
1. 上游（原材料/设备/核心零部件）、中游（制造/加工/核心环节）、下游（应用/终端需求）
2. 每个环节提炼 2-5 个关键子节点（具体到细分品类，如"覆铜板""铜箔""HDI 板"）
3. 标注"卡脖子"的关键环节，按以下标准分级：
   - high（高危）：国产化率 < 30%，完全或高度依赖进口，被列入出口管制清单
   - medium（中危）：国产化率 30-70%，部分可替代但高端仍进口，存在技术差距
   - low（关注）：国产化率 > 70%，已基本自主但个别规格仍不足
4. 不要编造股票代码或具体公司名（如果提到公司，放在 description 中）

返回严格 JSON（不要 markdown 标记）："""

USER_PROMPT_TEMPLATE = """分析「{sector_name}」行业的产业链结构。

{sector_context}

返回 JSON 格式：
{{
  "chain_nodes": [
    {{
      "id": "up_1",
      "name": "覆铜板",
      "type": "upstream",
      "description": "PCB 核心基材，高端高频板国产化率约 30%，仍依赖日本松下等",
      "keywords": ["覆铜板","CCL","铜箔"]
    }}
  ],
  "edges": [
    {{"source": "up_1", "target": "mid_1", "label": "供应基材"}}
  ],
  "bottlenecks": [
    {{"node_id": "up_1", "description": "高端覆铜板国产化率不足 30%", "severity": "high"}}
  ]
}}"""

# ── 别名映射（节省 LLM token，直接路由常见缩写）───────

ALIAS_MAP: Dict[str, str] = {
    "pcb": "PCB",
    "hbm": "HBM",
    "cpo": "CPO",
    "ai": "人工智能",
    "5g": "5G",
    "新能源车": "新能源汽车",
    "电动车": "新能源汽车",
}


class SectorChainService:
    """板块产业链分析服务。"""

    def __init__(self) -> None:
        self._manager: Optional[DataFetcherManager] = None

    @property
    def manager(self) -> DataFetcherManager:
        if self._manager is None:
            self._manager = DataFetcherManager()
        return self._manager

    # ── Public API ──────────────────────────────────────

    def analyze(self, sector_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        分析板块产业链（优先读缓存）。

        Args:
            sector_name: 板块名称
            force_refresh: 跳过缓存强制重新生成
        """
        resolved = ALIAS_MAP.get(sector_name.strip().lower(), sector_name.strip())
        if resolved != sector_name.strip():
            logger.info("[产业链] 别名映射: %s → %s", sector_name, resolved)

        # 优先查缓存
        if not force_refresh:
            cached = self._load_from_cache(resolved)
            if cached:
                cached["from_cache"] = True
                return cached

        # 缓存未命中 → 重新生成
        start = time.time()

        sector_context = self._build_sector_context()
        chain_data = self._llm_generate_chain(resolved, sector_context)
        if chain_data is None:
            return None

        chain_data = self._enrich_heat(chain_data, sector_context)
        chain_data["sector_name"] = resolved
        chain_data["generated_at"] = datetime.now(TZ_SHANGHAI).isoformat()
        chain_data["analysis_time_ms"] = int((time.time() - start) * 1000)
        chain_data["from_cache"] = False

        # 写入缓存
        self._save_to_cache(resolved, chain_data)

        logger.info(
            "[产业链] %s 完成: nodes=%d edges=%d bottlenecks=%d time=%dms",
            resolved,
            len(chain_data.get("chain_nodes", [])),
            len(chain_data.get("edges", [])),
            len(chain_data.get("bottlenecks", [])),
            chain_data["analysis_time_ms"],
        )
        return chain_data

    def _load_from_cache(self, sector_name: str) -> Optional[Dict[str, Any]]:
        try:
            from src.storage import DatabaseManager
            db = DatabaseManager()
            return db.get_sector_chain_cache(sector_name)
        except Exception as exc:
            logger.warning("[产业链] 读取缓存失败: %s", exc)
            return None

    def _save_to_cache(self, sector_name: str, chain_data: Dict[str, Any]) -> None:
        try:
            from src.storage import DatabaseManager
            db = DatabaseManager()
            db.set_sector_chain_cache(sector_name, chain_data)
        except Exception as exc:
            logger.warning("[产业链] 写入缓存失败: %s", exc)

    def list_available_sectors(self) -> List[Dict[str, Any]]:
        """列出可选的行业+概念板块（用于前端下拉）。"""
        all_sectors: List[Dict[str, Any]] = []
        seen = set()
        for source, getter in [
            ("industry", self.manager.get_sector_rankings),
            ("concept", self.manager.get_concept_rankings),
        ]:
            try:
                result = getter(50)
                items = (result[0] or []) + (result[1] or []) if result else []
                for item in items:
                    name = str(item.get("name", "")).strip()
                    if name and name not in seen:
                        seen.add(name)
                        all_sectors.append({"name": name, "change_pct": item.get("change_pct")})
            except Exception as exc:
                logger.warning("[产业链] 获取%s板块失败: %s", source, exc)

        all_sectors.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)
        return all_sectors

    def fuzzy_suggest(self, query: str, limit: int = 5) -> List[str]:
        """模糊匹配板块名，返回候选项。"""
        q = query.strip().lower()
        available = self.list_available_sectors()
        scored = []
        for s in available:
            nl = s["name"].lower()
            score = 0
            if q == nl:
                score = 100
            elif q in nl:
                score = 80
            elif nl in q:
                score = 60
            else:
                score = len(set(q) & set(nl)) * 10
            if score > 0:
                scored.append((s["name"], score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [x[0] for x in scored[:limit]]

    # ── Internal ────────────────────────────────────────

    def _build_sector_context(self) -> str:
        """构建市场板块热度上下文（只做必要的 akshare 请求）。"""
        lines = ["当前市场板块涨跌情况（供参考）："]

        # 只取行业板块排行（单次调用，新浪源稳定）
        try:
            result = self.manager.get_sector_rankings(8)
            if result and result[0]:
                tops = [f"{s['name']}({s.get('change_pct', 0):+.2f}%)" for s in result[0]]
                lines.append(f"  行业领涨: {', '.join(tops)}")
            if result and result[1]:
                bottoms = [f"{s['name']}({s.get('change_pct', 0):+.2f}%)" for s in result[1][:5]]
                lines.append(f"  行业领跌: {', '.join(bottoms)}")
        except Exception:
            pass

        if len(lines) == 1:
            return ""
        return "\n".join(lines)

    def _llm_generate_chain(self, sector_name: str, sector_context: str) -> Optional[Dict[str, Any]]:
        """调用 LLM 生成产业链拓扑（复用已配置的渠道 API key）。"""
        import litellm
        from src.llm.errors import call_litellm_with_param_recovery

        user = USER_PROMPT_TEMPLATE.format(
            sector_name=sector_name,
            sector_context=sector_context,
        )

        model = self._resolve_model()
        api_key = self._resolve_api_key_for_model(model)

        call_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": 8192,
            "timeout": 90,
            "response_format": {"type": "json_object"},
        }
        if api_key:
            call_kwargs["api_key"] = api_key

        logger.info("[产业链] 调用 LLM: model=%s sector=%s has_key=%s", model, sector_name, bool(api_key))

        try:
            response = call_litellm_with_param_recovery(
                call=lambda kwargs: litellm.completion(**kwargs),
                model=model,
                call_kwargs=call_kwargs,
                log_label="[产业链]",
            )
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("LLM returned empty content")
            return self._parse_json(content)
        except Exception as exc:
            logger.error("[产业链] LLM 调用失败: %s", exc)
            return None

    def _resolve_api_key_for_model(self, model: str) -> Optional[str]:
        """从 config 的 llm_channels 中查找对应模型的 API key。"""
        from src.config import get_config
        config = get_config()
        channels = getattr(config, "llm_channels", []) or []
        for ch in channels:
            ch_models = ch.get("models", [])
            if model in ch_models or any(m in model or model in m for m in ch_models):
                keys = ch.get("api_keys", [])
                if keys:
                    return str(keys[0])
                key = ch.get("api_key", "")
                if key:
                    return str(key)
        return None

    def _enrich_heat(self, chain_data: Dict[str, Any], sector_context: str) -> Dict[str, Any]:
        """用真实板块数据填充节点的热度评分。"""
        nodes = chain_data.get("chain_nodes", [])
        if not nodes:
            return chain_data

        # 从 sector_context 解析板块名→涨跌幅映射
        import re
        board_map: Dict[str, float] = {}
        for match in re.finditer(r"([^\s,]+?)\(([+-]?[\d.]+)%\)", sector_context):
            name = match.group(1).strip()
            try:
                board_map[name] = float(match.group(2))
            except ValueError:
                pass

        heat_nodes = []
        for node in nodes:
            node_id = node.get("id", "")
            node_name = node.get("name", "")
            keywords = node.get("keywords", [node_name])

            # 匹配真实板块
            matched_pct = None
            matched_board = None
            for kw in keywords:
                if kw in board_map:
                    matched_pct = board_map[kw]
                    matched_board = kw
                    break
                for board_name, pct in board_map.items():
                    if kw.lower() in board_name.lower():
                        matched_pct = pct
                        matched_board = board_name
                        break
                if matched_pct is not None:
                    break

            # 计算热度评分
            if matched_pct is not None:
                heat_score = min(100, max(0, 50 + matched_pct * 10))
                momentum = "up" if matched_pct > 0.5 else "down" if matched_pct < -0.5 else "stable"
                source = "market"  # 来自真实行情
                source_label = f"匹配板块「{matched_board}」"
            else:
                heat_score = 50
                momentum = "stable"
                source = "ai"  # AI 估算
                source_label = "AI 估算（无匹配板块）"

            heat_nodes.append({
                "node_id": node_id,
                "heat_score": round(heat_score),
                "change_pct": round(matched_pct, 2) if matched_pct is not None else None,
                "momentum": momentum,
                "matched_board": matched_board,
                "source": source,
                "source_label": source_label,
            })

        chain_data["heat_analysis"] = {"nodes": heat_nodes}
        return chain_data

    def _resolve_model(self) -> str:
        """解析当前可用的 LLM 模型。复用 Config 已解析的模型列表。"""
        from src.config import get_config
        config = get_config()

        # llm_channels 是 List[dict]，每个 dict 含 models 列表或 litellm_params
        channels = getattr(config, "llm_channels", []) or []
        for ch in channels:
            # 优先取 models 列表的第一个
            models = ch.get("models", [])
            if models:
                return str(models[0])
            # 兼容 litellm_params.model 格式
            lp = ch.get("litellm_params", {}) or {}
            if lp.get("model"):
                return str(lp["model"])

        # fallback: 从环境变量推测
        import os
        for key, model in [
            ("DEEPSEEK_API_KEY", "deepseek/deepseek-chat"),
            ("GEMINI_API_KEY", "gemini/gemini-2.0-flash"),
            ("ANTHROPIC_API_KEY", "claude-sonnet-4-6"),
            ("OPENAI_API_KEY", "gpt-4o"),
        ]:
            if os.getenv(key):
                return model

        raise RuntimeError("No LLM configured. Set LLM_CHANNELS or an API key in .env")

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        # 去 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            import re
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except json.JSONDecodeError:
                    pass
        logger.error("[产业链] JSON 解析失败: %.300s", text)
        return None
