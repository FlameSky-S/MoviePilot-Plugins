import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, c as createAutoRenewApi, u as unwrapResponse, e as errorMessage } from './_plugin-vue_export-helper-DbzU1Gkj.js';

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementBlock:_createElementBlock,createElementVNode:_createElementVNode} = await importShared('vue');


const _hoisted_1 = { class: "autorenew-config" };
const _hoisted_2 = {
  key: 1,
  class: "text-caption"
};
const _hoisted_3 = { class: "d-flex align-center mt-3 flex-wrap ga-2" };

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
};

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
  return out
}

const localConfig = ref({ ...DEFAULTS });
const status = ref(null);
const error = ref('');

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
                _createTextVNode(" 追踪 " + _toDisplayString(status.value?.tracked ?? '—') + " 部 ", 1)
              ]),
              _: 1
            }),
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
                  key: 0,
                  size: "small",
                  variant: "tonal",
                  color: status.value.auto_subscribe ? 'success' : 'warning'
                }, {
                  default: _withCtx(() => [
                    _createTextVNode(_toDisplayString(status.value.auto_subscribe ? '自动建订阅' : '仅提醒模式'), 1)
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
    _createVNode(_component_VAlert, {
      type: reminderOnly.value ? 'warning' : 'info',
      variant: "tonal",
      density: "compact",
      class: "mt-2"
    }, {
      default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
        _createTextVNode(" 关闭「自动建订阅」后进入", -1),
        _createElementVNode("strong", null, "仅提醒模式", -1),
        _createTextVNode("：仍会追踪并推送新季消息，但不会自动创建订阅。 名单增删只影响本插件，不会动 MoviePilot 里的订阅。 ", -1)
      ]))]),
      _: 1
    }, 8, ["type"]),
    _createElementVNode("div", _hoisted_3, [
      _createVNode(_component_VBtn, {
        color: "primary",
        variant: "flat",
        "prepend-icon": "mdi-content-save",
        onClick: submit
      }, {
        default: _withCtx(() => [...(_cache[8] || (_cache[8] = [
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
        default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
          _createTextVNode("刷新状态", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_VBtn, {
        variant: "text",
        "prepend-icon": "mdi-close",
        onClick: _cache[6] || (_cache[6] = $event => (emit('close')))
      }, {
        default: _withCtx(() => [...(_cache[10] || (_cache[10] = [
          _createTextVNode("关闭", -1)
        ]))]),
        _: 1
      })
    ])
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-815f20d2"]]);

export { Config as default };
