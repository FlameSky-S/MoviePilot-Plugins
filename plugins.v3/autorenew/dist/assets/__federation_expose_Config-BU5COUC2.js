import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { c as createAutoRenewApi, u as unwrapResponse, e as errorMessage } from './autoRenewApi-BX1ekatY.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,toDisplayString:_toDisplayString,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Config',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
},
  setup(__props, { expose: __expose }) {

/**
 * 插件设置页的 Vue 视图。
 * 宿主默认仍会渲染后端 `get_form()` 构建的原生表单；此组件作为补充视图，
 * 展示本插件的运行状态（只读），避免与原生表单字段产生歧义。
 */
const props = __props;

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`);
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase));

const status = ref(null);
const error = ref('');

async function load() {
  error.value = '';
  try {
    status.value = unwrapResponse(await pluginApi.value.status());
  } catch (err) {
    error.value = errorMessage(err);
  }
}

onMounted(load);

__expose({ load });

return (_ctx, _cache) => {
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createBlock(_component_VCard, {
    variant: "tonal",
    class: "ma-2"
  }, {
    default: _withCtx(() => [
      _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
        default: _withCtx(() => [...(_cache[0] || (_cache[0] = [
          _createTextVNode("自动续订 · 运行状态", -1)
        ]))]),
        _: 1
      }),
      _createVNode(_component_VCardText, null, {
        default: _withCtx(() => [
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
          (status.value)
            ? (_openBlock(), _createBlock(_component_VList, {
                key: 1,
                density: "compact"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VListItem, {
                    title: "插件状态",
                    subtitle: status.value.enabled ? '已启用' : '已停用'
                  }, null, 8, ["subtitle"]),
                  _createVNode(_component_VListItem, {
                    title: "追踪中",
                    subtitle: `${status.value.tracked} 部`
                  }, null, 8, ["subtitle"]),
                  _createVNode(_component_VListItem, {
                    title: "自动建订阅",
                    subtitle: status.value.auto_subscribe ? '开' : '仅提醒模式'
                  }, null, 8, ["subtitle"]),
                  _createVNode(_component_VListItem, {
                    title: "检测周期",
                    subtitle: status.value.cron
                  }, null, 8, ["subtitle"]),
                  _createVNode(_component_VListItem, {
                    title: "上次检测",
                    subtitle: status.value.last_run || '尚未执行'
                  }, null, 8, ["subtitle"])
                ]),
                _: 1
              }))
            : (_openBlock(), _createBlock(_component_VAlert, {
                key: 2,
                type: "info",
                variant: "tonal",
                density: "compact"
              }, {
                default: _withCtx(() => [...(_cache[1] || (_cache[1] = [
                  _createTextVNode("加载中…", -1)
                ]))]),
                _: 1
              }))
        ]),
        _: 1
      }),
      _createVNode(_component_VCardActions, null, {
        default: _withCtx(() => [
          _createVNode(_component_VBtn, {
            variant: "text",
            "prepend-icon": "mdi-refresh",
            onClick: load
          }, {
            default: _withCtx(() => [...(_cache[2] || (_cache[2] = [
              _createTextVNode("刷新", -1)
            ]))]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _: 1
  }))
}
}

};

export { _sfc_main as default };
