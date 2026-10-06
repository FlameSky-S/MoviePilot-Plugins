# MoviePilot-Plugins

FlameSky-S 的 **MoviePilot V3** 插件市场仓。

**只发 v3**：仓里只有 `package.v3.json` + `plugins.v3/`，刻意不带 `package.json` / `package.v2.json` / `plugins.v2/`。
（v3 宿主的市场回退链是 `v3 → v2 → package.json`，带上 v2 会在 v3 索引缺键或拉取失败时**静默装到 v2 实现**。CI 里有硬断言守住这条。）

## 安装

MoviePilot → 设置 → 插件市场，加入本仓地址：

```
https://github.com/FlameSky-S/MoviePilot-Plugins
```

## 插件列表

| 插件 | ID | 说明 |
| --- | --- | --- |
| 自动续订 | `AutoRenew` | 长期追踪电视剧：TMDB 上一出现新一季就自动建订阅。Sonarr 式的状态标签、季进度与播出日历。 |

### 自动续订（AutoRenew）

补的是 MoviePilot 的原生缺口（**不是配置问题**）：

- 宿主订阅是**按季**的 —— 一条订阅 = 一季，目标集补齐即完成并进历史，**不跨季**；
- 该季在 TMDB 上集数为 0 时**根本建不出订阅**（`chain/subscribe/create.py` 报「未获取到第 X 季的总集数」）。

所以「整剧长期监控、有下一季就续订」这件事由插件自己扛：维护一份长期追踪名单，
定时查 TMDB，发现「比已追踪季更大、且已有集数」的新季就调 `SubscribeChain.add` 建订阅。

细节见 [`plugins.v3/autorenew/README.md`](plugins.v3/autorenew/README.md)。

## 仓库约定

- 每个插件自带一套独立 Vite 工程（`vite.config.js` / `package.json` / `index.html` / `src/` 都在插件目录内，**无仓级 frontend workspace**）。
- **构建产物 `dist/` 提交进仓**（`.gitignore` 全局忽略 `dist/` 后反向放行 `!plugins.v3/*/dist/**`）；CI **不构建前端**，只做版本门禁 + 打 tag + 打包。
- `package.v3.json` 的 `version` ↔ 插件 `plugin_version` ↔ 插件内 `package.json` 的 `version` **三处必须一致**；`release: true` 的条目必须有 `history["v<version>"]`。这是 CI 门禁。
- tag 形如 `AutoRenew_v1.0.0`，资产形如 `autorenew_v1.0.0.zip`（zip 根目录直接是插件目录，含已提交的 dist）。

## 开发

```bash
# 后端纯逻辑单测（不需要 MoviePilot 运行环境）
python tests/run_tests.py

# 前端构建（产物需一并提交）
cd plugins.v3/autorenew && npm install && npm run build

# 本地跑版本门禁
python .github/scripts/check_plugin_versions.py package.v3.json

# 重新生成图标
python tools/gen_icon.py
```

## License

GPL-3.0
