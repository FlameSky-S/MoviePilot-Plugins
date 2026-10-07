"""续订规则的三级回退 —— 纯函数，不 import `app.*`，可裸机单测。

宿主侧的既有事实（决定了本模块的形状）：

1. 订阅行自带 `quality/resolution/sites/filter_groups/downloader/include/exclude`
   等列；空值时宿主自己会回退到全局默认：
   `chain/subscribe/query.py::get_params` 里就是
   `subscribe.quality or default_rule.get("quality")`。
2. 建订阅时传给 `SubscribeChain.add` 的 `**kwargs` 会被
   `application/subscription/write.py::_translate` 直接当成订阅行字段
   （媒体相关的同名字段由识别结果覆盖）。
3. 宿主把「空」落库成字符串 `"null"`（实测 `subscribe.sites` 就是），
   所以判定「有没有配」时必须把 `"null"` 当空。

因此本插件只要负责**在宿主全局默认之前补一层**：
该剧已有订阅的字段 → 插件设置 → 交给宿主。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

# 允许插件下发的订阅行字段（都是 `subscribe` 表真实存在的列）。
RULE_FIELDS: Sequence[str] = (
    "quality",
    "resolution",
    "sites",
    "filter_groups",
    "downloader",
    "include",
    "exclude",
)

# 宿主把空值写成这个字符串，不能当成「有配置」。
NULL_SENTINEL = "null"


def _is_set(value: Any) -> bool:
    """判断某个规则字段「确实配了值」。

    空字符串 / None / 空列表 / 空 dict / 字符串 `"null"` 都算没配 → 继续回退。
    """
    if value is None:
        return False
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and text.lower() != NULL_SENTINEL
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, Mapping):
        return len(value) > 0
    return True


def merge_rules(levels: Iterable[Optional[Mapping[str, Any]]]) -> Dict[str, Any]:
    """三级回退：**每个字段独立**取第一个「有值」的那一级。

    - 入参按优先级从高到低给：`[该剧已有订阅, 插件设置, 宿主全局]`。
    - 某一级里没配的字段**不出现在结果里** —— 结果里没有该键，调用方就不传，
      宿主才会用自己的全局默认（这是「回退到第三级」的正确表达方式，
      传 `None` / 空串反而会显式覆盖掉宿主的默认）。
    """
    out: Dict[str, Any] = {}
    for level in levels:
        if not level:
            continue
        for field in RULE_FIELDS:
            if field in out:
                continue
            value = level.get(field)
            if _is_set(value):
                out[field] = value
    return out


def rule_payload(config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """把插件配置里的规则项归一成一层可参与回退的 dict（第二级）。

    - 站点 / 过滤规则组：界面给的是字符串列表（multiselect），站点转 int；
    - 单值项（画质/分辨率/下载器/包含/排除）：去掉首尾空白，空串丢弃；
    - **只收 `RULE_FIELDS` 里列的键**，防止把界面上的无关字段带进订阅行。
    """
    config = config or {}
    out: Dict[str, Any] = {}

    sites: List[int] = []
    for raw in config.get("rules_sites") or []:
        try:
            sites.append(int(raw))
        except (TypeError, ValueError):
            continue
    if sites:
        out["sites"] = sites

    groups: List[str] = []
    for raw in config.get("rules_filter_groups") or []:
        # 只认字符串：`str(None)` 会变成 "None" 被误当成组名（单测抓过）
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if text and text.lower() != NULL_SENTINEL:
            groups.append(text)
    if groups:
        out["filter_groups"] = groups

    for key in ("quality", "resolution", "downloader", "include", "exclude"):
        value = config.get(f"rules_{key}")
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()

    return {k: v for k, v in out.items() if k in RULE_FIELDS}
