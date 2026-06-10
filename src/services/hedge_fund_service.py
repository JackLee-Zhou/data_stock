# -*- coding: utf-8 -*-
"""
大师会诊服务 — 多投资大师视角分析个股

复用项目现有数据（K线、技术指标、基本面），
13 位投资大师通过 LLM 各自给出买入/持有/卖出信号。

来源：AI Hedge Fund (https://github.com/virattt/ai-hedge-fund)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)
TZ_SHANGHAI = timezone(timedelta(hours=8))

# ── 大师定义 ───────────────────────────────────────

MASTERS: Dict[str, Dict[str, str]] = {
    "warren_buffett": {
        "name": "沃伦·巴菲特",
        "style": "价值投资，寻找有护城河、管理层优秀、估值合理的优质公司。偏好消费垄断型企业。",
        "signal_rules": "ROE>15%、负债低、有定价权的公司 bullish；高负债或不在能力圈内 bearish",
    },
    "ben_graham": {
        "name": "本·格雷厄姆",
        "style": "深度价值投资之父，只在有安全边际时买入。偏好低市盈率、低市净率的烟蒂股。",
        "signal_rules": "股价低于内在价值30%以上 bullish；高估值无安全边际 bearish",
    },
    "charlie_munger": {
        "name": "查理·芒格",
        "style": "以合理价格买入优秀公司，重视能力圈和跨学科思维。拒绝投机和频繁交易。",
        "signal_rules": "优秀公司+合理估值 bullish；平庸公司无论多便宜都 neutral/bearish",
    },
    "peter_lynch": {
        "name": "彼得·林奇",
        "style": "寻找十倍股，关注日常生活中的投资机会。偏好 PEG<1 的成长股。",
        "signal_rules": "PEG<1、业绩加速增长 bullish；成熟无增长 neutral；衰退 bearish",
    },
    "cathie_wood": {
        "name": "凯瑟琳·伍德",
        "style": "颠覆式创新投资，重仓AI、基因编辑、太空探索等前沿领域。不看短期估值。",
        "signal_rules": "颠覆性创新赛道+高研发投入 bullish；传统行业无创新 bearish",
    },
    "phil_fisher": {
        "name": "菲利普·费雪",
        "style": "成长股投资先驱，深度调研（scuttlebutt）。关注研发投入、管理层诚信。",
        "signal_rules": "高研发+高毛利+市场扩张 bullish；低研发投入保守行业 neutral",
    },
    "bill_ackman": {
        "name": "比尔·阿克曼",
        "style": "激进投资者，重仓少数标的，推动管理层变革。关注催化剂事件。",
        "signal_rules": "有明确催化剂+低估+管理层可施压 bullish；无催化剂 neutral",
    },
    "michael_burry": {
        "name": "迈克尔·伯里",
        "style": "逆向投资者，寻找市场定价错误的标的。关注资产负债表质量。",
        "signal_rules": "被市场过度悲观定价+资产负债表健康 bullish；高杠杆+泡沫 bearish",
    },
    "stanley_druckenmiller": {
        "name": "斯坦利·德鲁肯米勒",
        "style": "宏观对冲，寻找高确定性的非对称机会。关注流动性、政策、趋势。",
        "signal_rules": "行业上行+资金流入 bullish；政策打压+资金流出 bearish",
    },
    "nassim_taleb": {
        "name": "纳西姆·塔勒布",
        "style": "黑天鹅风险分析，关注尾部风险和凸性收益。反脆弱策略。",
        "signal_rules": "高波动+高潜在收益 bullish；表面稳定实脆弱 neutral/bearish",
    },
    "aswath_damodaran": {
        "name": "阿斯沃斯·达摩达兰",
        "style": "估值学教授，基于故事+数字+估值的系统框架。DCF 为核心工具。",
        "signal_rules": "内在价值>市价 bullish；差距<10% neutral；市值>内在价值 bearish",
    },
    "rakesh_jhunjhunwala": {
        "name": "拉克什·金君瓦拉",
        "style": "印度巴菲特，寻找被低估的中小盘成长股。关注新兴市场机会。",
        "signal_rules": "高成长+低估值+行业顺风 bullish；饱和市场+高估值 bearish",
    },
    "mohnish_pabrai": {
        "name": "莫尼什·帕布莱",
        "style": "克隆巴菲特策略，寻找'头重脚轻'的非对称机会。关注低风险高回报。",
        "signal_rules": "下有保底+上有空间 bullish；下行空间大于上行 bearish",
    },
}

SYSTEM_PROMPT_TEMPLATE = """你是一位著名投资大师。请基于提供的股票数据，按照你的投资哲学给出判断。

你的身份：{master_name}
你的投资风格：{master_style}
信号规则：{signal_rules}

返回 JSON（不要 markdown）：
{{"signal": "bullish"|"bearish"|"neutral", "confidence": 0-100, "reasoning": "理由（50字内中文）"}}"""


class HedgeFundService:
    """大师会诊服务。"""

    def analyze(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        所有大师并行分析一只股票。

        Returns:
            dict with masters dict + aggregated signal
        """
        start = time.time()

        # Step 1: 准备股票数据上下文
        data_context = self._build_stock_context(stock_code)
        if not data_context:
            return None

        # Step 2: 并行调用 LLM（顺序循环，避免并发复杂度）
        results: Dict[str, Dict] = {}
        for master_id, master_info in MASTERS.items():
            try:
                result = self._call_master(master_id, master_info, stock_code, data_context)
                if result:
                    results[master_id] = {**result, "name": master_info["name"]}
                    logger.info("[大师会诊] %s(%s): %s %d%%",
                                master_info["name"], master_id, result["signal"], result["confidence"])
            except Exception as exc:
                logger.warning("[大师会诊] %s 分析失败: %s", master_info["name"], exc)
                results[master_id] = {
                    "name": master_info["name"],
                    "signal": "neutral",
                    "confidence": 50,
                    "reasoning": f"分析异常: {exc}",
                }

        # Step 3: 聚合信号
        aggregated = self._aggregate(results)

        return {
            "stock_code": stock_code,
            "masters": results,
            "aggregated": aggregated,
            "generated_at": datetime.now(TZ_SHANGHAI).isoformat(),
            "analysis_time_ms": int((time.time() - start) * 1000),
        }

    def _build_stock_context(self, code: str) -> str:
        """构建股票数据上下文（复用现有数据管道）。"""
        try:
            from src.storage import DatabaseManager
            db = DatabaseManager()
            ctx = db.get_analysis_context(code)
            if not ctx:
                logger.warning("[大师会诊] 无 %s 的数据", code)
                return ""
            # 提取关键信息
            lines = [f"股票代码: {code}"]
            for key in ("latest_close", "ma5", "ma10", "ma20", "volume_ratio",
                         "latest_pct_chg", "turnover_rate"):
                if key in ctx:
                    lines.append(f"{key}: {ctx[key]}")
            for key in ("pe_ratio", "pb_ratio", "total_mv", "circ_mv"):
                if ctx.get(key):
                    lines.append(f"{key}: {ctx[key]}")
            return "\n".join(lines)
        except Exception as exc:
            logger.error("[大师会诊] 获取数据失败: %s", exc)
            return f"股票代码: {code}（数据获取失败）"

    def _call_master(self, master_id: str, info: Dict, code: str, ctx: str) -> Optional[Dict]:
        """调用 LLM 让一位大师分析。"""
        import litellm
        from src.llm.errors import call_litellm_with_param_recovery
        from src.config import get_config

        config = get_config()
        model = self._resolve_model(config)

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            master_name=info["name"],
            master_style=info["style"],
            signal_rules=info["signal_rules"],
        )

        call_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"股票: {code}\n数据:\n{ctx}"},
            ],
            "temperature": 0.7,
            "max_tokens": 300,
            "timeout": 30,
        }

        # 注入 API key
        api_key = self._resolve_api_key(config)
        if api_key:
            call_kwargs["api_key"] = api_key

        response = call_litellm_with_param_recovery(
            call=lambda kwargs: litellm.completion(**kwargs),
            model=model,
            call_kwargs=call_kwargs,
            log_label="[大师会诊]",
        )
        content = response.choices[0].message.content or "{}"
        return self._parse_json(content)

    def _aggregate(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """聚合所有大师信号为综合判断。"""
        bullish = sum(1 for r in results.values() if r.get("signal") == "bullish")
        bearish = sum(1 for r in results.values() if r.get("signal") == "bearish")
        neutral = sum(1 for r in results.values() if r.get("signal") == "neutral")
        total = len(results) or 1

        avg_confidence = sum(r.get("confidence", 50) for r in results.values()) / total

        if bullish > bearish and bullish > neutral:
            signal = "bullish"
        elif bearish > bullish and bearish > neutral:
            signal = "bearish"
        else:
            signal = "neutral"

        return {
            "signal": signal,
            "confidence": round(avg_confidence),
            "bullish_count": bullish,
            "bearish_count": bearish,
            "neutral_count": neutral,
            "total_masters": total,
        }

    @staticmethod
    def _resolve_model(config) -> str:
        """从配置中解析 LLM 模型。"""
        channels = getattr(config, "llm_channels", []) or []
        for ch in channels:
            models = ch.get("models", [])
            if models:
                return str(models[0])
        import os
        for key, model in [("DEEPSEEK_API_KEY", "deepseek/deepseek-chat")]:
            if os.getenv(key):
                return model
        raise RuntimeError("No LLM configured")

    @staticmethod
    def _resolve_api_key(config) -> Optional[str]:
        channels = getattr(config, "llm_channels", []) or []
        for ch in channels:
            keys = ch.get("api_keys", [])
            if keys:
                return str(keys[0])
            key = ch.get("api_key", "")
            if key:
                return str(key)
        return None

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:] if lines[0].startswith("```") else lines
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
        return None
