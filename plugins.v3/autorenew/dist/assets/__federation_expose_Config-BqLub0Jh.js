import { importShared } from './__federation_fn_import-JrT3xvdd.js';

function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

function errorMessage(error) {
  if (!error) return ''
  if (typeof error === 'string') return error
  return error.message || error.reason || String(error)
}

function seasonLabel(season) {
  const number = Number(season ?? 0);
  return number > 0 ? `第 ${number} 季` : '特别季'
}

function formatDate(value) {
  if (!value) return ''
  const text = String(value).slice(0, 10);
  return text || ''
}

function resolvePluginBase(pluginBase) {
  const raw = typeof pluginBase === 'function' ? pluginBase() : (pluginBase?.value ?? pluginBase);
  return raw || 'plugin/AutoRenew'
}

/**
 * 宿主通过 `api` prop 注入调用器：路径是 `plugin/<PluginId><endpoint>`。
 */
function createAutoRenewApi(api, pluginBase) {
  const get = endpoint => api.get(`${resolvePluginBase(pluginBase)}${endpoint}`);
  const post = (endpoint, payload) => api.post(`${resolvePluginBase(pluginBase)}${endpoint}`, payload);
  const query = params => {
    const search = new URLSearchParams(params || {}).toString();
    return search ? `?${search}` : ''
  };

  return {
    unwrapResponse,
    status() {
      return get('/status')
    },
    shows() {
      return get('/shows')
    },
    addShow(payload) {
      return post('/shows/add', payload)
    },
    removeShow(payload) {
      return post('/shows/remove', payload)
    },
    toggleShow(payload) {
      return post('/shows/toggle', payload)
    },
    showSeasons(params) {
      return get(`/shows/seasons?${params.toString()}`)
    },
    search(params) {
      return get(`/search?${params.toString()}`)
    },
    /** 导入前比对：返回 {added, removed, kept, library_total, last_sync}。 */
    importPreview(params = {}) {
      return get(`/import_preview${query(params)}`)
    },
    /** 按确认结果执行：{add: [tmdbid], remove: [tmdbid]}。 */
    importApply(payload = {}) {
      return post('/import_apply', payload)
    },
    /** 重新拉 TMDB 元数据：{scope: 'ended' | 'all'}。 */
    refresh(payload = { scope: 'ended' }) {
      return post('/refresh', payload)
    },
    calendar(params = {}) {
      return get(`/calendar${query(params)}`)
    },
    /** 续订规则候选项：{sites, filter_groups, downloaders, quality_choices, resolution_choices}。 */
    ruleOptions() {
      return get('/rule_options')
    },
    /** 读取本插件配置（页面内「设置」入口回显用）。 */
    config() {
      return get('/config')
    },
    /** 保存本插件配置：后端 update_config + 立即 init_plugin 生效。 */
    saveConfig(payload) {
      return post('/config', payload)
    },
    check() {
      return post('/check', {})
    },
  }
}

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = { class: "autorenew-config" };
const _hoisted_2 = {
  key: 2,
  class: "text-caption"
};
const _hoisted_3 = { class: "d-flex align-center flex-wrap ga-2 mb-1" };
const _hoisted_4 = { class: "d-flex align-center mt-3 flex-wrap ga-2" };

const {computed,onMounted,ref} = await importShared('vue');

const DEFAULT_CRON = '0 */6 * * *';


const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
},
  emits: ['save', 'close'],
  setup(__props, { expose: __expose, emit: __emit }) {

/**
 * 插件设置页。
 *
 * ⚠️ 宿主的设置弹窗 `PluginConfigDialog` 会加载本组件的联邦 `./Config`，
 * **它取代后端 `get_form()` 渲染的原生表单**（实测：`loadRemoteComponent(id, 'Config')`，
 * 且只有 `errorComponent`、没有回落原生表单的兜底）。所以设置项必须在这里渲染，
 * 光写 `get_form()` 用户看不到任何可配置项。
 *
 * 宿主契约（实测自 `public/assets` 的 PluginConfigDialog）：
 *   props : initial-config / api / plugin-id / source-plugin-id / native-subscribe
 *   emits : save / close   —— 宿主收到 save 的载荷后自己 PUT /api/v1/plugin/<id>
 * 因此表单状态由本组件持有，点保存只需 emit('save', 配置对象)。
 */
const props = __props;

const emit = __emit;

const DEFAULTS = {
  enabled: false,
  auto_subscribe: true,
  notify: true,
  poll_cron: DEFAULT_CRON,
  max_actions_per_run: 5,
  show_sidebar_nav: true,
  // 续订规则（第二级回退）：留空 = 交给 MoviePilot 全局默认
  rules_quality: '',
  rules_resolution: '',
  rules_sites: [],
  rules_filter_groups: [],
  rules_downloader: '',
  rules_include: '',
  rules_exclude: '',
};

const RULE_TEXT_KEYS = [
  'rules_quality',
  'rules_resolution',
  'rules_downloader',
  'rules_include',
  'rules_exclude',
];

/** 只认这几个键，脏值一律回落默认（宿主可能传缺字段或字符串过来）。 */
function normalizeConfig(raw) {
  const source = raw && typeof raw === 'object' ? raw : {};
  const out = { ...DEFAULTS };
  for (const key of Object.keys(DEFAULTS)) {
    if (source[key] !== undefined && source[key] !== null) out[key] = source[key];
  }
  out.enabled = !!out.enabled;
  out.auto_subscribe = !!out.auto_subscribe;
  out.notify = !!out.notify;
  out.show_sidebar_nav = !!out.show_sidebar_nav;
  out.poll_cron = String(out.poll_cron || '').trim() || DEFAULT_CRON;
  const limit = Number.parseInt(out.max_actions_per_run, 10);
  out.max_actions_per_run = Number.isFinite(limit) && limit > 0 ? limit : DEFAULTS.max_actions_per_run;
  // 站点/规则组存字符串数组（后端 rule_payload 会把站点转 int）
  out.rules_sites = Array.isArray(out.rules_sites) ? out.rules_sites.map(String) : [];
  out.rules_filter_groups = Array.isArray(out.rules_filter_groups)
    ? out.rules_filter_groups.map(String)
    : [];
  for (const key of RULE_TEXT_KEYS) out[key] = String(out[key] ?? '').trim();
  return out
}

const localConfig = ref({ ...DEFAULTS });
const status = ref(null);
const error = ref('');
/** 续订规则候选项，从宿主现读（站点 / 过滤规则组 / 下载器）。 */
const ruleOptions = ref({ sites: [], filter_groups: [], downloaders: [], quality_choices: [], resolution_choices: [] });

const siteItems = computed(() =>
  (ruleOptions.value.sites || []).map(site => ({
    title: `${site.name}${site.public ? ' · 公开站' : ''}`,
    value: String(site.id),
  })),
);
const groupItems = computed(() =>
  (ruleOptions.value.filter_groups || []).map(name => ({ title: name, value: name })),
);
const downloaderItems = computed(() =>
  (ruleOptions.value.downloaders || []).map(name => ({ title: name, value: name })),
);
/** 有多少条规则字段真的配了值（用来提示是否已接管默认）。 */
const configuredRuleCount = computed(
  () =>
    RULE_TEXT_KEYS.filter(key => localConfig.value[key]).length +
    (localConfig.value.rules_sites?.length ? 1 : 0) +
    (localConfig.value.rules_filter_groups?.length ? 1 : 0),
);

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`);
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase));
const reminderOnly = computed(() => !localConfig.value.auto_subscribe);
const cronError = computed(() => {
  const segments = String(localConfig.value.poll_cron || '').trim().split(/\s+/).filter(Boolean);
  return segments.length === 5 ? '' : 'crontab 需要 5 段，例如 0 */6 * * *'
});

async function loadStatus() {
  try {
    status.value = unwrapResponse(await pluginApi.value.status());
  } catch (err) {
    error.value = errorMessage(err);
  }
}

async function loadRuleOptions() {
  try {
    const res = unwrapResponse(await pluginApi.value.ruleOptions());
    if (res && typeof res === 'object') ruleOptions.value = { ...ruleOptions.value, ...res };
  } catch (err) {
    // 候选项拿不到不该挡住设置页，用户可以手填
    error.value = `续订规则候选项加载失败（仍可手填）：${errorMessage(err)}`;
  }
}

function submit() {
  if (cronError.value) {
    error.value = cronError.value;
    return
  }
  error.value = '';
  emit('save', {
    ...localConfig.value,
    poll_cron: String(localConfig.value.poll_cron).trim(),
    max_actions_per_run:
      Number.parseInt(localConfig.value.max_actions_per_run, 10) || DEFAULTS.max_actions_per_run,
  });
}

onMounted(() => {
  localConfig.value = normalizeConfig(props.initialConfig);
  loadStatus();
  loadRuleOptions();
});

__expose({ load: loadStatus });

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VCombobox = _resolveComponent("VCombobox");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VSpacer = _resolveComponent("VSpacer");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "error",
          variant: "tonal",
          density: "compact",
          class: "mb-3"
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(_component_VCard, {
      variant: "tonal",
      class: "mb-3"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardText, { class: "d-flex align-center flex-wrap ga-2 py-2" }, {
          default: _withCtx(() => [
            _createVNode(_component_VChip, {
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-television"
            }, {
              default: _withCtx(() => [
                _createTextVNode(" 追踪 " + _toDisplayString(status.value?.tracking ?? status.value?.tracked ?? '—') + " 部 ", 1)
              ]),
              _: 1
            }),
            (status.value?.terminated)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 0,
                  size: "small",
                  variant: "tonal",
                  title: '已完结 / 已砍，已停止轮询；合计 ' + (status.value?.tracked ?? 0) + ' 部'
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(" 已完结 " + _toDisplayString(status.value.terminated) + " 部 ", 1)
                  ]),
                  _: 1
                }, 8, ["title"]))
              : _createCommentVNode("", true),
            _createVNode(_component_VChip, {
              size: "small",
              variant: "tonal",
              "prepend-icon": "mdi-clock-outline"
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(status.value?.cron || DEFAULT_CRON), 1)
              ]),
              _: 1
            }),
            (status.value)
              ? (_openBlock(), _createBlock(_component_VChip, {
                  key: 1,
                  size: "small",
                  variant: "tonal",
                  color: status.value.auto_subscribe ? 'success' : 'warning'
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(status.value.auto_subscribe ? '自动续订已开启' : '仅提醒模式'), 1)
                  ]),
                  _: 1
                }, 8, ["color"]))
              : _createCommentVNode("", true),
            (status.value?.last_run)
              ? (_openBlock(), _createElementBlock("span", _hoisted_2, "上次检测 " + _toDisplayString(status.value.last_run), 1))
              : _createCommentVNode("", true)
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VRow, { dense: "" }, {
      default: _withCtx(() => [
        _createVNode(_component_VCol, {
          cols: "12",
          md: "4"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: localConfig.value.enabled,
              "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((localConfig.value.enabled) = $event)),
              label: "启用插件",
              density: "compact",
              "hide-details": "",
              color: "primary"
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "4"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: localConfig.value.auto_subscribe,
              "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((localConfig.value.auto_subscribe) = $event)),
              label: "发现新季时自动建订阅",
              density: "compact",
              "hide-details": "",
              color: "primary"
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "4"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: localConfig.value.notify,
              "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((localConfig.value.notify) = $event)),
              label: "发送通知",
              density: "compact",
              "hide-details": "",
              color: "primary"
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VRow, { dense: "" }, {
      default: _withCtx(() => [
        _createVNode(_component_VCol, {
          cols: "12",
          md: "6"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VTextField, {
              modelValue: localConfig.value.poll_cron,
              "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((localConfig.value.poll_cron) = $event)),
              label: "检测周期（crontab）",
              "error-messages": cronError.value,
              density: "compact",
              variant: "outlined",
              "persistent-hint": "",
              hint: "默认 0 */6 * * *，即每 6 小时查一次 TMDB"
            }, null, 8, ["modelValue", "error-messages"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VTextField, {
              modelValue: localConfig.value.max_actions_per_run,
              "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((localConfig.value.max_actions_per_run) = $event)),
              modelModifiers: { number: true },
              label: "每轮最多建几条订阅",
              type: "number",
              min: "1",
              density: "compact",
              variant: "outlined",
              "persistent-hint": "",
              hint: "限速，防止一次对站点发起过多搜索"
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSwitch, {
              modelValue: localConfig.value.show_sidebar_nav,
              "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((localConfig.value.show_sidebar_nav) = $event)),
              label: "显示侧边菜单入口",
              density: "compact",
              "hide-details": "",
              color: "primary"
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VDivider, { class: "my-3" }),
    _createElementVNode("div", _hoisted_3, [
      _cache[14] || (_cache[14] = _createElementVNode("span", { class: "text-subtitle-2" }, "续订规则", -1)),
      _createVNode(_component_VChip, {
        size: "x-small",
        variant: "tonal",
        color: configuredRuleCount.value ? 'success' : 'grey'
      }, {
        default: _withCtx(() => [
          _createTextVNode(_toDisplayString(configuredRuleCount.value ? `已配 ${configuredRuleCount.value} 项` : '全部跟随 MoviePilot 全局'), 1)
        ]),
        _: 1
      }, 8, ["color"])
    ]),
    _cache[20] || (_cache[20] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-3" }, [
      _createTextVNode(" 新建订阅按三级回退取值："),
      _createElementVNode("strong", null, "该剧已有订阅的参数 → 这里的设置 → MoviePilot 全局默认"),
      _createTextVNode("。 留空的项目"),
      _createElementVNode("strong", null, "不写进订阅"),
      _createTextVNode("，由 MoviePilot 用自己的全局默认兜底。 ")
    ], -1)),
    _createVNode(_component_VRow, { dense: "" }, {
      default: _withCtx(() => [
        _createVNode(_component_VCol, {
          cols: "12",
          md: "6"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSelect, {
              modelValue: localConfig.value.rules_filter_groups,
              "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((localConfig.value.rules_filter_groups) = $event)),
              items: groupItems.value,
              label: "过滤规则组",
              multiple: "",
              chips: "",
              "closable-chips": "",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              "menu-props": { maxHeight: 320 }
            }, null, 8, ["modelValue", "items"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "6"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSelect, {
              modelValue: localConfig.value.rules_sites,
              "onUpdate:modelValue": _cache[7] || (_cache[7] = $event => ((localConfig.value.rules_sites) = $event)),
              items: siteItems.value,
              label: "订阅站点",
              multiple: "",
              chips: "",
              "closable-chips": "",
              density: "compact",
              variant: "outlined",
              "hide-details": "",
              "menu-props": { maxHeight: 320 }
            }, null, 8, ["modelValue", "items"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VRow, {
      dense: "",
      class: "mt-1"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCol, {
          cols: "12",
          md: "3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VSelect, {
              modelValue: localConfig.value.rules_downloader,
              "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((localConfig.value.rules_downloader) = $event)),
              items: downloaderItems.value,
              label: "下载器",
              clearable: "",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue", "items"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCombobox, {
              modelValue: localConfig.value.rules_resolution,
              "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((localConfig.value.rules_resolution) = $event)),
              items: ruleOptions.value.resolution_choices || [],
              label: "分辨率",
              clearable: "",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue", "items"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VCombobox, {
              modelValue: localConfig.value.rules_quality,
              "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((localConfig.value.rules_quality) = $event)),
              items: ruleOptions.value.quality_choices || [],
              label: "画质",
              clearable: "",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue", "items"])
          ]),
          _: 1
        }),
        _createVNode(_component_VCol, {
          cols: "12",
          md: "3"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VTextField, {
              modelValue: localConfig.value.rules_include,
              "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((localConfig.value.rules_include) = $event)),
              label: "包含关键词",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VRow, {
      dense: "",
      class: "mt-1"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCol, {
          cols: "12",
          md: "6"
        }, {
          default: _withCtx(() => [
            _createVNode(_component_VTextField, {
              modelValue: localConfig.value.rules_exclude,
              "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((localConfig.value.rules_exclude) = $event)),
              label: "排除关键词",
              density: "compact",
              variant: "outlined",
              "hide-details": ""
            }, null, 8, ["modelValue"])
          ]),
          _: 1
        })
      ]),
      _: 1
    }),
    _createVNode(_component_VAlert, {
      type: reminderOnly.value ? 'warning' : 'info',
      variant: "tonal",
      density: "compact",
      class: "mt-2"
    }, {
      default: _withCtx(() => [...(_cache[15] || (_cache[15] = [
        _createTextVNode(" 关闭「自动建订阅」后进入", -1),
        _createElementVNode("strong", null, "仅提醒模式", -1),
        _createTextVNode("：仍会追踪并推送新季消息，但不会自动创建订阅。 名单增删只影响本插件，不会动 MoviePilot 里的订阅。 ", -1)
      ]))]),
      _: 1
    }, 8, ["type"]),
    _createElementVNode("div", _hoisted_4, [
      _createVNode(_component_VBtn, {
        color: "primary",
        variant: "flat",
        "prepend-icon": "mdi-content-save",
        onClick: submit
      }, {
        default: _withCtx(() => [...(_cache[16] || (_cache[16] = [
          _createTextVNode(" 保存 ", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_VSpacer),
      _createVNode(_component_VBtn, {
        variant: "text",
        "prepend-icon": "mdi-refresh",
        onClick: loadStatus
      }, {
        default: _withCtx(() => [...(_cache[17] || (_cache[17] = [
          _createTextVNode("刷新状态", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_VBtn, {
        variant: "text",
        "prepend-icon": "mdi-filter-outline",
        onClick: loadRuleOptions
      }, {
        default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
          _createTextVNode(" 重载规则候选 ", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_VBtn, {
        variant: "text",
        "prepend-icon": "mdi-close",
        onClick: _cache[13] || (_cache[13] = $event => (emit('close')))
      }, {
        default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
          _createTextVNode("关闭", -1)
        ]))]),
        _: 1
      })
    ])
  ]))
}
}

};
const ConfigPanel = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-dcfb6669"]]);

export { _export_sfc as _, createAutoRenewApi as c, ConfigPanel as default, errorMessage as e, formatDate as f, seasonLabel as s, unwrapResponse as u };
