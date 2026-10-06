# 自动续订（AutoRenew）

给 MoviePilot 补上 Sonarr 式的**整剧长期监控**：一部剧进了追踪名单，之后 TMDB 上
一出现「比已追踪季更大、且已经有集数」的新一季，就自动去建订阅。

## 为什么需要它

MoviePilot 原生**没有**跨季续订能力，这是设计使然、不是没配好：

| 宿主事实 | 出处 | 后果 |
| --- | --- | --- |
| 订阅按季：一条订阅 = 一季，目标集补齐即完成并进历史 | `chain/subscribe/completion.py` | 本季完结后不会自动接上下一季 |
| 该季 TMDB 集数为 0 时建不出订阅 | `chain/subscribe/create.py::__store_subscribe_episode_total` | 提前订下一季也不行，会报「未获取到第 X 季的总集数」 |
| 订阅完成的记录会被写历史并删除 | `SubscribeCompleteEventData` | 想长期追踪必须自己落库，别指望事后查 `subscribe` 表 |

所以缺口正好落在**季与季之间**（本季播完 → 隔年才出下一季）。本插件把这段自己扛起来。

## 功能

- **侧边菜单入口**：MoviePilot 侧栏「订阅」区出现「自动续订」（Vue 模块联邦页面）。
- **追踪名单**三条来源：TMDB 搜索手动添加 / 监听 `subscribe.added` 自动同步 / 从媒体库批量导入。
- **Sonarr 式状态标签**：TMDB `status` 直译中文（连载中 / 已续订 / 制作中 / 试播集 / 已完结 / 已砍），
  外加派生徽标（有新季可订阅 / 新季已确认待开播 / 已追平 / 已暂停续订）。
- **季进度弹窗**：每季的 TMDB 集数、媒体库内集数、状态（已入库 / 待下载 / 未播出）、首播日。
- **播出日历**：未来 N 天已确认的下一集日期。
- **自动建订阅**：可关（关掉即「仅提醒」模式，只推消息不动订阅）。
- **限速**：每轮最多建 N 条订阅，默认 5，防止一次性对站点发起过多搜索。

## 安装

插件市场加入 `https://github.com/FlameSky-S/MoviePilot-Plugins`，安装「自动续订」。
要求 MoviePilot `>=3.0.0,<4`。

## 配置

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| 启用插件 | 关 | 总开关 |
| 发现新季时自动建订阅 | 开 | 关掉 = 仅提醒模式 |
| 发送通知 | 开 | 新建订阅与汇总都走 MoviePilot 通知渠道 |
| 检测周期（crontab） | `0 */6 * * *` | 每 6 小时查一次 TMDB |
| 每轮最多建几条订阅 | 5 | 限速 |
| 显示侧边菜单入口 | 开 | 关掉则侧栏不出现该项 |

## 冷启动

**不会**在首次启用时批量补订阅。请打开侧栏「自动续订」页面，点右下角按钮里的
**「从媒体库导入」**——它只把媒体库里的剧集**纳入追踪名单**，不创建任何订阅。
之后是否续订由检测逻辑按上面的规则决定。

> 从名单里移除某部剧，**不会**动 MoviePilot 里的订阅；名单和订阅是两回事。

## 数据存放

名单以 JSON 数组存在宿主 `plugindata` 表（`plugin_id='AutoRenew'`, `key='watchlist'`），
没有自建数据库表。

## 插件 API

前缀 `/api/v1/plugin/AutoRenew`，`auth: bear`（与内置 Vue 工作台插件一致）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/status` | 运行状态与统计 |
| GET | `/shows?sort=next_airing\|recent` | 追踪名单 |
| POST | `/shows/add` | 加入追踪 |
| POST | `/shows/remove` | 移出追踪（不动订阅） |
| POST | `/shows/toggle` | 开关单部剧自动续订 |
| GET | `/shows/seasons?tmdbid=` | 某剧各季的库内 / 待下载 / 未播出状态 |
| GET | `/search?keyword=` | 搜索 TMDB 剧集 |
| POST | `/import_library` | 从媒体库导入（不建订阅） |
| GET | `/calendar?days=30` | 未来播出日历 |
| POST | `/check` | 立即执行一次检测 |

## 已知边界

- 只有「新季在 TMDB 上已有集数」时才能建订阅——这是宿主限制，不是本插件的取舍。
- **特别季 S0 被排除**：不作为续订目标，也不进日历。
- 状态为 `Ended` / `Canceled` 且没有更新的季 → 停止轮询，页面折叠到「已完结」区灰显。
- v1 不做「完结守卫」（不拦截宿主把订阅标记完成）。

## 开发

```bash
# 纯逻辑单测（不需要 MoviePilot 运行环境）
python tests/run_tests.py
```

`core/` 下的 `models.py` / `renewal.py` / `store.py` **只依赖标准库**，是刻意拆出来的深水区：
续订判定是可测的纯函数，宿主耦合全部收在 `core/tmdb.py` 与 `__init__.py`。
