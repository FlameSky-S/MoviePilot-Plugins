"""插件对外的 HTTP 路由表。

宿主给 `path` 加 `/<plugin_id>` 前缀，最终是 `/api/v1/plugin/AutoRenew/...`；
前端通过宿主注入的 `api.get('plugin/AutoRenew/shows')` 调用。
`auth: "bear"` 与内置 Vue 工作台插件（brushflow / subtitlemanualupload）保持一致。
"""

from __future__ import annotations

from typing import Any, Dict, List


def build_api_routes(owner: Any) -> List[Dict[str, Any]]:
    return [
        {
            "path": "/status",
            "endpoint": owner.api_status,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "插件状态与统计",
        },
        {
            "path": "/shows",
            "endpoint": owner.api_list_shows,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "追踪名单",
        },
        {
            "path": "/shows/add",
            "endpoint": owner.api_add_show,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "加入追踪名单",
        },
        {
            "path": "/shows/remove",
            "endpoint": owner.api_remove_show,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "移出追踪名单（不动 MP 订阅）",
        },
        {
            "path": "/shows/toggle",
            "endpoint": owner.api_toggle_show,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "开关单部剧的自动续订",
        },
        {
            "path": "/shows/seasons",
            "endpoint": owner.api_show_seasons,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "某剧各季的库内/待下载状态",
        },
        {
            "path": "/search",
            "endpoint": owner.api_search,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "搜索 TMDB 剧集",
        },
        {
            "path": "/import_preview",
            "endpoint": owner.api_import_preview,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "媒体库导入前比对（将新增 / 将移除）",
        },
        {
            "path": "/import_apply",
            "endpoint": owner.api_import_apply,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "按确认结果执行媒体库导入",
        },
        {
            "path": "/refresh",
            "endpoint": owner.api_refresh,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "重新拉取 TMDB 元数据（scope=ended|all）",
        },
        {
            "path": "/calendar",
            "endpoint": owner.api_calendar,
            "methods": ["GET"],
            "auth": "bear",
            "summary": "未来播出日历",
        },
        {
            "path": "/check",
            "endpoint": owner.api_check,
            "methods": ["POST"],
            "auth": "bear",
            "summary": "立即执行一次新季检测",
        },
    ]
