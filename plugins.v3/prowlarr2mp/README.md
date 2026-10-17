# Prowlarr2MP

把 **Prowlarr** 里配置的索引器（**公开 / 半公开 / 私有**全收录）桥接进 **MoviePilot**，让 MoviePilot 的搜索、订阅与下载都能覆盖这些站点。

## 来源（改自哪个插件）

| 项 | 内容 |
| --- | --- |
| 原始插件 | [`mitlearn/MoviePilot-PluginsV2`](https://github.com/mitlearn/MoviePilot-PluginsV2) → `plugins.v3/prowlarr2mp`（Prowlarr 索引器，v2.0.0，MIT） |
| 它的上游 | [`jtcymc/MoviePilot-PluginsV2`](https://github.com/jtcymc/MoviePilot-PluginsV2) |
| 本插件相对原始插件的改动 | ① **去掉公开站过滤**（原版默认只收 halfPrivate/private，public 直接 `continue`）；② **修「分类误伤」**（原版分类探测失败/无影视分类时整条丢弃索引器，改为兜底 Torznab `2000`/`5000`）；③ 保留原版的**手动加站**模型（`SitesHelper.add_indexer` 注册 + 站点管理手动加 domain），**不写宿主站点库**；④ 适配 v3.1.0 的 `TorrentInfo` 真实签名（原版传 `imdbid=` 会被 `TypeError` 吞掉整条结果）。 |

> 依赖的是**重写后的 V3 分支**（类名 `Prowlarr2MP`、插件 ID `Prowlarr2MP`），不是 jtcymc 的 v2 版本。

---

## ✨ 功能

- 从 Prowlarr `GET /api/v1/indexer` 拉取已启用索引器
- **收录 public / semiPrivate / private 全部索引器**（不再过滤公开站）
- 通过 MoviePilot 模块钩子 `search_torrents` 以 Prowlarr `GET /api/v1/search` 聚合搜索（真正的检索由 Prowlarr 完成）
- 分类识别（Torznab `2000` 电影 / `5000` 剧集）、促销识别（freeleech / halfleech / doubleupload）
- 中文关键词自动回退英文标题补搜
- RSS 订阅与 Spider 浏览
- HTTP API、远程命令、AI 智能体工具

---

## 🚀 快速开始

### 前置要求

- MoviePilot v3.x（`system_version >= 3.0.0`）
- Prowlarr v1.0+，且其中已配置并启用至少一个索引器

### 安装

**方式一：插件市场（本仓）**

1. 设置 → 插件 → 插件市场 → 右上角齿轮 → 添加仓库：

   ```
   https://github.com/FlameSky-S/MoviePilot-Plugins
   ```

2. 更新后在列表中找到 **Prowlarr2MP** 并安装。

**方式二：手动**

```bash
cp -r plugins.v3/prowlarr2mp /path/to/moviepilot/plugins/
# 重启 MoviePilot
```

### 配置

| 配置项 | 说明 | 必填 |
|---|---|---|
| 启用插件 | 总开关 | ✅ |
| 服务器地址 | Prowlarr 地址，含 `http://` 或 `https://`，如 `http://prowlarr:9696` | ✅ |
| API 密钥 | Prowlarr → 设置 → 通用 → 安全 → API 密钥 | ✅ |
| 同步周期 | Cron 表达式，默认 `0 0 */12 * *`（每 12 小时） | ❌ |
| 使用代理 | 通过 MoviePilot 系统代理访问 Prowlarr | ❌ |
| 立即运行一次 | 保存后立即同步索引器列表 | ❌ |

---

## ⚠️ 重要：手动加站（必须执行）

> 本插件**不写宿主站点库**。索引器要参与搜索，必须手动在「站点管理」里添加对应站点，否则插件无法参与搜索。

1. 填好配置 → 保存并启用「**立即运行一次**」，等待同步完成。
2. 打开 **设置 → 插件 → Prowlarr2MP**，在插件详情页查看每个索引器的 **站点 domain**（形如 `prowlarr2mp.<id>`）。
3. 打开 **设置 → 站点管理 → 添加站点**：
   - **站点地址**：填入该 domain（如 `prowlarr2mp.12`）
   - 站点名称 / Cookie / UA：可留空或随意填（插件会忽略这些字段）
   - 保存
4. 对**每个**要使用的索引器重复第 2–3 步。
5. 在 MoviePilot 搜索框用**英文关键词**（如 `The Matrix`）测试，结果里应能看到对应站点的资源。

> **批量技巧**：插件详情页的表格可直接复制 domain；也可用 MoviePilot API 脚本批量添加。

---

## ❓ 常见问题

<details>
<summary><b>Q：站点管理里的"测试连接"失败？</b></summary>

已知限制。插件使用虚拟域名（如 `prowlarr2mp.12`），MoviePilot 会尝试 DNS 解析它，因此失败属正常，**不影响搜索**。站点可用性以 Prowlarr 内的测试为准。
</details>

<details>
<summary><b>Q：提示"未搜索到数据"但实际有结果？</b></summary>

MoviePilot 统计插件返回数量时可能漏计。以搜索结果页/日志里"站点搜索完成，有效资源数"为准。
</details>

<details>
<summary><b>Q：为什么中文关键词搜不到？</b></summary>

Prowlarr 对中文支持有限。插件会对中文关键词自动用英文标题补搜一次；仍建议直接使用英文关键词。
</details>

<details>
<summary><b>Q：哪些索引器被过滤了？</b></summary>

本插件只过滤**纯成人（XXX）分类**的索引器。日志关键词 `过滤`（如 `过滤仅XXX分类站点`）。
</details>

---

## 🔧 工作原理

1. `GET {prowlarr}/api/v1/indexer` 拉取已启用索引器；逐个 `GET {prowlarr}/api/v1/indexer/{id}` 取分类（Torznab）并映射为 MoviePilot 的 movie/tv 分类。
2. 通过 `SitesHelper().add_indexer(domain, indexer_dict)` 把索引器注册进 MoviePilot 的内建索引器支持范围（domain = `prowlarr2mp.<id>`）。
3. 用户在「站点管理」手动添加以该 domain 为地址的站点，使其进入搜索范围。
4. 搜索时，MoviePilot 调用插件的模块钩子 `search_torrents`，由插件代向 Prowlarr `GET /api/v1/search` 发起查询，再把结果转成 `TorrentInfo` 返回；下载链接取 Prowlarr 返回的 `downloadUrl`（无则 `magnetUrl`）。

> 与宿主站点库（`SiteOper`）写入方案不同：本插件不落库，因此**无卸载残留问题**，但代价是需要手动加站，且站点记录不在宿主库中。

---

## 📄 许可

上游 `mitlearn/MoviePilot-PluginsV2` 与 `jtcymc/MoviePilot-PluginsV2` 均为 **MIT**。MIT 与 GPL-3.0 兼容，本插件随本仓整体以 **GPL-3.0** 发布（见仓根 `LICENSE`），保留上游版权与许可声明。
