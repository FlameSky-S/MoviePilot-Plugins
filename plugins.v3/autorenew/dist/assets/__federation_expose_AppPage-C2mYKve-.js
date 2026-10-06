import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc, c as createAutoRenewApi, s as seasonLabel, f as formatDate, u as unwrapResponse, e as errorMessage } from './_plugin-vue_export-helper-DbzU1Gkj.js';

const {toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createVNode:_createVNode,createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,createElementBlock:_createElementBlock,unref:_unref,withModifiers:_withModifiers,mergeProps:_mergeProps,Teleport:_Teleport,withKeys:_withKeys} = await importShared('vue');


const _hoisted_1 = { class: "autorenew-app" };
const _hoisted_2 = { class: "d-flex align-center flex-wrap ga-2 mb-3" };
const _hoisted_3 = { class: "d-flex align-center justify-center fill-height" };
const _hoisted_4 = { class: "text-body-2 font-weight-medium text-truncate" };
const _hoisted_5 = { class: "d-flex align-center flex-wrap ga-1 mt-1" };
const _hoisted_6 = {
  key: 0,
  class: "text-caption mt-1"
};
const _hoisted_7 = { class: "d-flex align-center flex-wrap ga-2 mb-2" };
const _hoisted_8 = { class: "text-subtitle-2" };
const _hoisted_9 = { class: "text-body-2 text-truncate" };
const _hoisted_10 = { class: "autorenew-fab-host" };
const _hoisted_11 = { class: "text-caption text-medium-emphasis mb-3" };
const _hoisted_12 = { class: "text-subtitle-2 mb-1" };
const _hoisted_13 = { class: "text-caption text-medium-emphasis" };
const _hoisted_14 = { class: "text-subtitle-2 mb-1" };

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
  navKey: { type: String, default: 'main' },
  hideTitle: { type: Boolean, default: false },
},
  setup(__props, { expose: __expose }) {

/**
 * 自动续订工作台。
 * 数据全部经宿主注入的 `api` 调 `/api/v1/plugin/AutoRenew/*`。
 */
const props = __props;

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`);
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase));

const SORTS = [
  { value: 'next_airing', title: 'Next Airing' },
  { value: 'recent', title: '最近添加' },
];

const loading = ref(false);
const busy = ref(false);
const message = ref('');
const error = ref('');
const shows = ref([]);
const status = ref(null);
const sort = ref('next_airing');
const fabOpen = ref(false);

const searchOpen = ref(false);
const searchKeyword = ref('');
const searchResults = ref([]);
const searching = ref(false);

const calendarOpen = ref(false);
const calendarEvents = ref([]);

const detailOpen = ref(false);
const detail = ref(null);

// 「从媒体库导入」确认流程
const importOpen = ref(false);
const importPreview = ref(null);
const importSync = ref(false);
const importBusy = ref(false);
const addSelected = ref([]);
const removeSelected = ref([]);

const refreshingEnded = ref(false);

const activeShows = computed(() => shows.value.filter(show => !show.terminated));
const endedShows = computed(() => shows.value.filter(show => show.terminated));
/** 全局「仅提醒模式」时，单剧的续订开关没有任何作用 —— UI 要禁用而不是假装能点。 */
const reminderOnly = computed(() => !!status.value && !status.value.auto_subscribe);

async function load() {
  loading.value = true;
  error.value = '';
  try {
    const [list, info] = await Promise.all([
      pluginApi.value.shows(sort.value),
      pluginApi.value.status(),
    ]);
    shows.value = unwrapResponse(list) || [];
    status.value = unwrapResponse(info);
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    loading.value = false;
  }
}

async function changeSort() {
  await load();
}

async function toggleRenew(show) {
  try {
    const res = unwrapResponse(
      await pluginApi.value.toggleShow({ tmdbid: show.tmdbid, auto_renew: !show.auto_renew }),
    );
    if (res?.auto_renew !== undefined) show.auto_renew = res.auto_renew;
    await load(); // 徽标与排序会随开关变化，整体重载最稳
  } catch (err) {
    error.value = errorMessage(err);
  }
}

/** 已完结区：重新拉 TMDB 元数据（万一那边又续订了，状态要能跟着变）。 */
async function refreshEnded() {
  refreshingEnded.value = true;
  error.value = '';
  try {
    const res = unwrapResponse(await pluginApi.value.refresh({ scope: 'ended' }));
    message.value = res?.message || '已刷新';
    await load();
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    refreshingEnded.value = false;
  }
}

async function removeShow(show) {
  try {
    const res = unwrapResponse(await pluginApi.value.removeShow({ tmdbid: show.tmdbid }));
    message.value = res?.message || '已移出追踪名单';
    await load();
  } catch (err) {
    error.value = errorMessage(err);
  }
}

async function openDetail(show) {
  detail.value = { ...show, seasons: [] };
  detailOpen.value = true;
  try {
    const res = unwrapResponse(
      await pluginApi.value.showSeasons(new URLSearchParams({ tmdbid: show.tmdbid })),
    );
    detail.value = { ...show, ...(res || {}) };
  } catch (err) {
    error.value = errorMessage(err);
  }
}

async function runSearch() {
  if (!searchKeyword.value.trim()) return
  searching.value = true;
  error.value = '';
  try {
    const res = await pluginApi.value.search(
      new URLSearchParams({ keyword: searchKeyword.value.trim() }),
    );
    searchResults.value = unwrapResponse(res) || [];
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    searching.value = false;
  }
}

async function addShow(item, season = 1) {
  try {
    const res = unwrapResponse(
      await pluginApi.value.addShow({
        tmdbid: item.tmdbid,
        title: item.title,
        year: item.year,
        season,
        poster_path: item.poster_path,
      }),
    );
    message.value = res?.message || '已加入追踪';
    item.tracked = true;
    await load();
  } catch (err) {
    error.value = errorMessage(err);
  }
}

/** 打开确认弹窗：先比对一次，默认全勾。 */
async function openImport() {
  importOpen.value = true;
  importSync.value = false;
  await loadImportPreview();
}

/**
 * 比对。「先强制同步媒体库再比对」打开时会调宿主 `MediaServerChain.sync`
 * 跑一遍全库同步（较慢），换来「库里已删除的剧」也能被立刻识别出来。
 */
async function loadImportPreview() {
  importBusy.value = true;
  error.value = '';
  try {
    const res = unwrapResponse(await pluginApi.value.importPreview({ sync: importSync.value }));
    importPreview.value = res;
    addSelected.value = (res?.added || []).map(item => item.tmdbid);
    removeSelected.value = (res?.removed || []).map(item => item.tmdbid);
    if (res?.sync_note) message.value = res.sync_note;
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    importBusy.value = false;
  }
}

function toggleSelected(listRef, tmdbid) {
  const index = listRef.value.indexOf(tmdbid);
  if (index >= 0) listRef.value.splice(index, 1);
  else listRef.value.push(tmdbid);
}

async function applyImport() {
  importBusy.value = true;
  error.value = '';
  try {
    const res = unwrapResponse(
      await pluginApi.value.importApply({ add: addSelected.value, remove: removeSelected.value }),
    );
    message.value = res?.message || '导入完成';
    importOpen.value = false;
    await load();
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    importBusy.value = false;
  }
}

async function runCheck() {
  busy.value = true;
  error.value = '';
  try {
    const res = unwrapResponse(await pluginApi.value.check());
    const result = res?.result || {};
    message.value = `检测完成：检查 ${result.checked ?? 0} 部，新建订阅 ${(result.renewed || []).length} 条`;
    await load();
  } catch (err) {
    error.value = errorMessage(err);
  } finally {
    busy.value = false;
  }
}

async function openCalendar() {
  calendarOpen.value = true;
  try {
    const res = unwrapResponse(await pluginApi.value.calendar({ days: 60 }));
    calendarEvents.value = res?.events || [];
  } catch (err) {
    error.value = errorMessage(err);
  }
}

onMounted(load);

__expose({ load, loading });

return (_ctx, _cache) => {
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VImg = _resolveComponent("VImg");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VContainer = _resolveComponent("VContainer");
  const _component_VFab = _resolveComponent("VFab");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VMenu = _resolveComponent("VMenu");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VAvatar = _resolveComponent("VAvatar");
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent("VListItemSubtitle");
  const _component_VDialog = _resolveComponent("VDialog");
  const _component_VTable = _resolveComponent("VTable");
  const _component_VCheckbox = _resolveComponent("VCheckbox");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VContainer, {
      fluid: "",
      class: "pa-3"
    }, {
      default: _withCtx(() => [
        (error.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 0,
              type: "error",
              variant: "tonal",
              density: "compact",
              closable: "",
              class: "mb-3",
              "onClick:close": _cache[0] || (_cache[0] = $event => (error.value = ''))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(error.value), 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (message.value)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 1,
              type: "success",
              variant: "tonal",
              density: "compact",
              closable: "",
              class: "mb-3",
              "onClick:close": _cache[1] || (_cache[1] = $event => (message.value = ''))
            }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(message.value), 1)
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        _createElementVNode("div", _hoisted_2, [
          (status.value)
            ? (_openBlock(), _createBlock(_component_VChip, {
                key: 0,
                size: "small",
                variant: "tonal",
                "prepend-icon": "mdi-television"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" 追踪 " + _toDisplayString(status.value.tracked) + " 部 ", 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (status.value)
            ? (_openBlock(), _createBlock(_component_VChip, {
                key: 1,
                size: "small",
                variant: "tonal",
                "prepend-icon": "mdi-clock-outline"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(status.value.cron), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          (status.value)
            ? (_openBlock(), _createBlock(_component_VChip, {
                key: 2,
                size: "small",
                color: status.value.auto_subscribe ? 'success' : 'warning',
                variant: "tonal"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(_toDisplayString(status.value.auto_subscribe ? '自动建订阅' : '仅提醒模式'), 1)
                ]),
                _: 1
              }, 8, ["color"]))
            : _createCommentVNode("", true),
          _createVNode(_component_VSpacer),
          _createVNode(_component_VSelect, {
            modelValue: sort.value,
            "onUpdate:modelValue": [
              _cache[2] || (_cache[2] = $event => ((sort).value = $event)),
              changeSort
            ],
            items: SORTS,
            density: "compact",
            variant: "outlined",
            "hide-details": "",
            style: {"max-width":"180px"}
          }, null, 8, ["modelValue"]),
          _createVNode(_component_VBtn, {
            icon: "mdi-refresh",
            variant: "text",
            size: "small",
            loading: loading.value,
            onClick: load
          }, null, 8, ["loading"])
        ]),
        (!loading.value && !shows.value.length)
          ? (_openBlock(), _createBlock(_component_VAlert, {
              key: 2,
              type: "info",
              variant: "tonal"
            }, {
              default: _withCtx(() => [...(_cache[18] || (_cache[18] = [
                _createTextVNode(" 追踪名单还是空的。点右下角按钮「从媒体库导入」，或「添加剧集」搜索 TMDB。 ", -1)
              ]))]),
              _: 1
            }))
          : _createCommentVNode("", true),
        _createVNode(_component_VRow, { dense: "" }, {
          default: _withCtx(() => [
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(activeShows.value, (show) => {
              return (_openBlock(), _createBlock(_component_VCol, {
                key: show.tmdbid,
                cols: "6",
                sm: "4",
                md: "3",
                lg: "2"
              }, {
                default: _withCtx(() => [
                  _createVNode(_component_VCard, {
                    class: "h-100",
                    variant: "flat",
                    onClick: $event => (openDetail(show))
                  }, {
                    default: _withCtx(() => [
                      _createVNode(_component_VImg, {
                        src: show.poster_url || '',
                        "aspect-ratio": "0.68",
                        cover: "",
                        class: "bg-grey-darken-3"
                      }, {
                        placeholder: _withCtx(() => [
                          _createElementVNode("div", _hoisted_3, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-television",
                              size: "48"
                            })
                          ])
                        ]),
                        _: 1
                      }, 8, ["src"]),
                      _createVNode(_component_VCardText, { class: "pa-2" }, {
                        default: _withCtx(() => [
                          _createElementVNode("div", _hoisted_4, _toDisplayString(show.title), 1),
                          _createElementVNode("div", _hoisted_5, [
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              variant: "tonal"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(show.status_label), 1)
                              ]),
                              _: 2
                            }, 1024),
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              variant: "tonal",
                              color: "primary"
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(_unref(seasonLabel)(show.season)), 1)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _createVNode(_component_VChip, {
                            size: "x-small",
                            variant: "tonal",
                            class: "mt-1",
                            color: "secondary"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(show.badge), 1)
                            ]),
                            _: 2
                          }, 1024),
                          (show.next_episode_air_date)
                            ? (_openBlock(), _createElementBlock("div", _hoisted_6, " 下一集 " + _toDisplayString(_unref(formatDate)(show.next_episode_air_date)), 1))
                            : _createCommentVNode("", true)
                        ]),
                        _: 2
                      }, 1024),
                      _createVNode(_component_VCardActions, { class: "pa-1" }, {
                        default: _withCtx(() => [
                          _createVNode(_component_VTooltip, {
                            text: 
                  reminderOnly.value
                    ? '全局已设为「仅提醒模式」，单剧开关暂不生效'
                    : '参与自动续订：发现新季时自动建订阅'
                ,
                            location: "top"
                          }, {
                            activator: _withCtx(({ props: switchProps }) => [
                              _createVNode(_component_VSwitch, _mergeProps({ ref_for: true }, switchProps, {
                                "model-value": show.auto_renew,
                                disabled: reminderOnly.value,
                                density: "compact",
                                "hide-details": "",
                                label: "续订",
                                onClick: _cache[3] || (_cache[3] = _withModifiers(() => {}, ["stop"])),
                                "onUpdate:modelValue": $event => (toggleRenew(show))
                              }), null, 16, ["model-value", "disabled", "onUpdate:modelValue"])
                            ]),
                            _: 2
                          }, 1032, ["text"]),
                          _createVNode(_component_VSpacer),
                          _createVNode(_component_VTooltip, {
                            text: "移出追踪名单（不影响 MoviePilot 里的订阅）",
                            location: "top"
                          }, {
                            activator: _withCtx(({ props: deleteProps }) => [
                              _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, deleteProps, {
                                icon: "mdi-delete-outline",
                                size: "x-small",
                                variant: "text",
                                onClick: _withModifiers($event => (removeShow(show)), ["stop"])
                              }), null, 16, ["onClick"])
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024)
                    ]),
                    _: 2
                  }, 1032, ["onClick"])
                ]),
                _: 2
              }, 1024))
            }), 128))
          ]),
          _: 1
        }),
        (endedShows.value.length)
          ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
              _createVNode(_component_VDivider, { class: "my-4" }),
              _createElementVNode("div", _hoisted_7, [
                _createElementVNode("span", _hoisted_8, " 已完结 / 已砍（停止轮询）· " + _toDisplayString(endedShows.value.length) + " 部 ", 1),
                _createVNode(_component_VSpacer),
                _createVNode(_component_VTooltip, {
                  text: "重新向 TMDB 拉取这些剧的状态与季信息",
                  location: "top"
                }, {
                  activator: _withCtx(({ props: refreshProps }) => [
                    _createVNode(_component_VBtn, _mergeProps(refreshProps, {
                      size: "small",
                      variant: "text",
                      "prepend-icon": "mdi-refresh",
                      loading: refreshingEnded.value,
                      onClick: _withModifiers(refreshEnded, ["stop"])
                    }), {
                      default: _withCtx(() => [...(_cache[19] || (_cache[19] = [
                        _createTextVNode(" 刷新 TMDB 信息 ", -1)
                      ]))]),
                      _: 1
                    }, 16, ["loading"])
                  ]),
                  _: 1
                })
              ]),
              _createVNode(_component_VRow, { dense: "" }, {
                default: _withCtx(() => [
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(endedShows.value, (show) => {
                    return (_openBlock(), _createBlock(_component_VCol, {
                      key: show.tmdbid,
                      cols: "6",
                      sm: "4",
                      md: "3",
                      lg: "2"
                    }, {
                      default: _withCtx(() => [
                        _createVNode(_component_VCard, {
                          class: "h-100",
                          variant: "tonal",
                          style: {"opacity":"0.6"},
                          onClick: $event => (openDetail(show))
                        }, {
                          default: _withCtx(() => [
                            _createVNode(_component_VCardText, { class: "pa-2" }, {
                              default: _withCtx(() => [
                                _createElementVNode("div", _hoisted_9, _toDisplayString(show.title), 1),
                                _createVNode(_component_VChip, {
                                  size: "x-small",
                                  variant: "tonal",
                                  class: "mt-1"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(show.status_label), 1)
                                  ]),
                                  _: 2
                                }, 1024)
                              ]),
                              _: 2
                            }, 1024)
                          ]),
                          _: 2
                        }, 1032, ["onClick"])
                      ]),
                      _: 2
                    }, 1024))
                  }), 128))
                ]),
                _: 1
              })
            ], 64))
          : _createCommentVNode("", true)
      ]),
      _: 1
    }),
    (_openBlock(), _createBlock(_Teleport, { to: "body" }, [
      _createElementVNode("div", _hoisted_10, [
        _createVNode(_component_VMenu, {
          modelValue: fabOpen.value,
          "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((fabOpen).value = $event)),
          location: "top end",
          offset: "16"
        }, {
          activator: _withCtx(({ props: activatorProps }) => [
            _createVNode(_component_VFab, _mergeProps(activatorProps, {
              icon: "mdi-dots-grid",
              size: "large",
              color: "primary",
              elevation: "8",
              loading: busy.value
            }), null, 16, ["loading"])
          ]),
          default: _withCtx(() => [
            _createVNode(_component_VList, {
              density: "compact",
              "min-width": "200"
            }, {
              default: _withCtx(() => [
                _createVNode(_component_VListItem, {
                  "prepend-icon": "mdi-magnify",
                  title: "添加剧集",
                  onClick: _cache[4] || (_cache[4] = $event => (searchOpen.value = true))
                }),
                _createVNode(_component_VListItem, {
                  "prepend-icon": "mdi-calendar-month",
                  title: "播出日历",
                  onClick: openCalendar
                }),
                _createVNode(_component_VListItem, {
                  "prepend-icon": "mdi-sync",
                  title: "立即检查",
                  onClick: runCheck
                }),
                _createVNode(_component_VListItem, {
                  "prepend-icon": "mdi-library-shelves",
                  title: "从媒体库导入…",
                  onClick: openImport
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        }, 8, ["modelValue"])
      ])
    ])),
    _createVNode(_component_VDialog, {
      modelValue: searchOpen.value,
      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((searchOpen).value = $event)),
      "max-width": "720"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx(() => [...(_cache[20] || (_cache[20] = [
                _createTextVNode("添加剧集", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VTextField, {
                  modelValue: searchKeyword.value,
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((searchKeyword).value = $event)),
                  label: "剧名",
                  density: "compact",
                  variant: "outlined",
                  "hide-details": "",
                  "append-inner-icon": "mdi-magnify",
                  onKeyup: _withKeys(runSearch, ["enter"]),
                  "onClick:appendInner": runSearch
                }, null, 8, ["modelValue"]),
                (searching.value)
                  ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                      key: 0,
                      indeterminate: "",
                      class: "mt-2"
                    }))
                  : _createCommentVNode("", true),
                (searchResults.value.length)
                  ? (_openBlock(), _createBlock(_component_VList, {
                      key: 1,
                      density: "compact",
                      class: "mt-2"
                    }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(searchResults.value, (item) => {
                          return (_openBlock(), _createBlock(_component_VListItem, {
                            key: item.tmdbid
                          }, {
                            prepend: _withCtx(() => [
                              _createVNode(_component_VAvatar, {
                                rounded: "",
                                size: "40"
                              }, {
                                default: _withCtx(() => [
                                  _createVNode(_component_VImg, {
                                    src: item.poster_url || ''
                                  }, null, 8, ["src"])
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            append: _withCtx(() => [
                              (item.tracked)
                                ? (_openBlock(), _createBlock(_component_VChip, {
                                    key: 0,
                                    size: "small",
                                    variant: "tonal"
                                  }, {
                                    default: _withCtx(() => [...(_cache[21] || (_cache[21] = [
                                      _createTextVNode("已追踪", -1)
                                    ]))]),
                                    _: 1
                                  }))
                                : (_openBlock(), _createBlock(_component_VBtn, {
                                    key: 1,
                                    size: "small",
                                    variant: "text",
                                    onClick: $event => (addShow(item, 1))
                                  }, {
                                    default: _withCtx(() => [...(_cache[22] || (_cache[22] = [
                                      _createTextVNode("加入", -1)
                                    ]))]),
                                    _: 1
                                  }, 8, ["onClick"]))
                            ]),
                            default: _withCtx(() => [
                              _createVNode(_component_VListItemTitle, { class: "text-body-2" }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.title), 1)
                                ]),
                                _: 2
                              }, 1024),
                              _createVNode(_component_VListItemSubtitle, { class: "text-caption" }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(item.year || '年份未知'), 1)
                                ]),
                                _: 2
                              }, 1024)
                            ]),
                            _: 2
                          }, 1024))
                        }), 128))
                      ]),
                      _: 1
                    }))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[7] || (_cache[7] = $event => (searchOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[23] || (_cache[23] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: detailOpen.value,
      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((detailOpen).value = $event)),
      "max-width": "640"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx(() => [
                _createTextVNode(_toDisplayString(detail.value?.title) + " · " + _toDisplayString(_unref(seasonLabel)(detail.value?.tracked_season || 0)) + "已追踪 ", 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VTable, { density: "compact" }, {
                  default: _withCtx(() => [
                    _cache[24] || (_cache[24] = _createElementVNode("thead", null, [
                      _createElementVNode("tr", null, [
                        _createElementVNode("th", null, "季"),
                        _createElementVNode("th", null, "TMDB 集数"),
                        _createElementVNode("th", null, "库内集数"),
                        _createElementVNode("th", null, "状态"),
                        _createElementVNode("th", null, "首播")
                      ])
                    ], -1)),
                    _createElementVNode("tbody", null, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(detail.value?.seasons || [], (season) => {
                        return (_openBlock(), _createElementBlock("tr", {
                          key: season.season_number
                        }, [
                          _createElementVNode("td", null, _toDisplayString(season.season_number), 1),
                          _createElementVNode("td", null, _toDisplayString(season.episode_count), 1),
                          _createElementVNode("td", null, _toDisplayString(season.in_library), 1),
                          _createElementVNode("td", null, [
                            _createVNode(_component_VChip, {
                              size: "x-small",
                              variant: "tonal",
                              color: season.tracked ? 'primary' : ''
                            }, {
                              default: _withCtx(() => [
                                _createTextVNode(_toDisplayString(season.state), 1)
                              ]),
                              _: 2
                            }, 1032, ["color"])
                          ]),
                          _createElementVNode("td", null, _toDisplayString(_unref(formatDate)(season.air_date) || '—'), 1)
                        ]))
                      }), 128))
                    ])
                  ]),
                  _: 1
                }),
                (!detail.value?.seasons?.length)
                  ? (_openBlock(), _createBlock(_component_VAlert, {
                      key: 0,
                      type: "info",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
                        _createTextVNode(" 未取到季信息。 ", -1)
                      ]))]),
                      _: 1
                    }))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[9] || (_cache[9] = $event => (detailOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: calendarOpen.value,
      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((calendarOpen).value = $event)),
      "max-width": "560"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
                _createTextVNode("未来 60 天播出", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                (calendarEvents.value.length)
                  ? (_openBlock(), _createBlock(_component_VList, {
                      key: 0,
                      density: "compact"
                    }, {
                      default: _withCtx(() => [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(calendarEvents.value, (event) => {
                          return (_openBlock(), _createBlock(_component_VListItem, {
                            key: `${event.date}-${event.tmdbid}`,
                            title: event.title,
                            subtitle: `${event.date} · ${event.status_label}`,
                            "prepend-icon": "mdi-calendar-blank"
                          }, null, 8, ["title", "subtitle"]))
                        }), 128))
                      ]),
                      _: 1
                    }))
                  : (_openBlock(), _createBlock(_component_VAlert, {
                      key: 1,
                      type: "info",
                      variant: "tonal",
                      density: "compact"
                    }, {
                      default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                        _createTextVNode(" 暂无已确认的近期播出。TMDB 上未公布下一集日期的剧不会出现在这里。 ", -1)
                      ]))]),
                      _: 1
                    }))
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[11] || (_cache[11] = $event => (calendarOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[29] || (_cache[29] = [
                    _createTextVNode("关闭", -1)
                  ]))]),
                  _: 1
                })
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: importOpen.value,
      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((importOpen).value = $event)),
      "max-width": "720",
      scrollable: ""
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, { class: "text-subtitle-1" }, {
              default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                _createTextVNode("从媒体库导入", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [
                _createVNode(_component_VAlert, {
                  type: "info",
                  variant: "tonal",
                  density: "compact",
                  class: "mb-3"
                }, {
                  default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                    _createTextVNode(" 只影响本插件的追踪名单，", -1),
                    _createElementVNode("strong", null, "不会创建任何 MoviePilot 订阅", -1),
                    _createTextVNode("。 ", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VSwitch, {
                  modelValue: importSync.value,
                  "onUpdate:modelValue": [
                    _cache[13] || (_cache[13] = $event => ((importSync).value = $event)),
                    loadImportPreview
                  ],
                  label: "先强制同步媒体库再比对",
                  density: "compact",
                  "hide-details": "",
                  color: "primary",
                  disabled: importBusy.value
                }, null, 8, ["modelValue", "disabled"]),
                _createElementVNode("div", _hoisted_11, [
                  _cache[33] || (_cache[33] = _createTextVNode(" 宿主每 6 小时自动同步一次媒体库；打开这项会立刻跑一遍全库同步（较慢）， 这样「已从库里删除的剧」也能马上被识别出来。 ", -1)),
                  (importPreview.value?.last_sync)
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                        _cache[32] || (_cache[32] = _createElementVNode("br", null, null, -1)),
                        _createTextVNode("当前缓存最近更新：" + _toDisplayString(importPreview.value.last_sync), 1)
                      ], 64))
                    : _createCommentVNode("", true)
                ]),
                (importBusy.value)
                  ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                      key: 0,
                      indeterminate: "",
                      class: "mb-3"
                    }))
                  : _createCommentVNode("", true),
                (importPreview.value)
                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                      _createElementVNode("div", _hoisted_12, [
                        _createTextVNode(" 将新增 " + _toDisplayString(importPreview.value.added.length) + " 部 ", 1),
                        _createElementVNode("span", _hoisted_13, " （库内共 " + _toDisplayString(importPreview.value.library_total) + " 部，名单内已有 " + _toDisplayString(importPreview.value.kept) + " 部） ", 1)
                      ]),
                      (importPreview.value.added.length)
                        ? (_openBlock(), _createBlock(_component_VList, {
                            key: 0,
                            density: "compact",
                            class: "mb-3"
                          }, {
                            default: _withCtx(() => [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(importPreview.value.added, (item) => {
                                return (_openBlock(), _createBlock(_component_VListItem, {
                                  key: `add-${item.tmdbid}`,
                                  title: item.title,
                                  subtitle: `TMDB ${item.tmdbid} · 库内最高第 ${item.season} 季`
                                }, {
                                  prepend: _withCtx(() => [
                                    _createVNode(_component_VCheckbox, {
                                      "model-value": addSelected.value.includes(item.tmdbid),
                                      density: "compact",
                                      "hide-details": "",
                                      color: "primary",
                                      onClick: _cache[14] || (_cache[14] = _withModifiers(() => {}, ["stop"])),
                                      "onUpdate:modelValue": $event => (toggleSelected(addSelected.value, item.tmdbid))
                                    }, null, 8, ["model-value", "onUpdate:modelValue"])
                                  ]),
                                  _: 2
                                }, 1032, ["title", "subtitle"]))
                              }), 128))
                            ]),
                            _: 1
                          }))
                        : (_openBlock(), _createBlock(_component_VAlert, {
                            key: 1,
                            type: "success",
                            variant: "tonal",
                            density: "compact",
                            class: "mb-3"
                          }, {
                            default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                              _createTextVNode(" 没有需要新增的剧。 ", -1)
                            ]))]),
                            _: 1
                          })),
                      _createElementVNode("div", _hoisted_14, "将移除 " + _toDisplayString(importPreview.value.removed.length) + " 部", 1),
                      _cache[36] || (_cache[36] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-2" }, " 只列出「来源 = 媒体库导入」且现在库里已找不到的剧；手动添加、订阅同步进来的永不在此列。 ", -1)),
                      (importPreview.value.removed.length)
                        ? (_openBlock(), _createBlock(_component_VList, {
                            key: 2,
                            density: "compact"
                          }, {
                            default: _withCtx(() => [
                              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(importPreview.value.removed, (item) => {
                                return (_openBlock(), _createBlock(_component_VListItem, {
                                  key: `del-${item.tmdbid}`,
                                  title: item.title,
                                  subtitle: `TMDB ${item.tmdbid} · 媒体库里已找不到`
                                }, {
                                  prepend: _withCtx(() => [
                                    _createVNode(_component_VCheckbox, {
                                      "model-value": removeSelected.value.includes(item.tmdbid),
                                      density: "compact",
                                      "hide-details": "",
                                      color: "error",
                                      onClick: _cache[15] || (_cache[15] = _withModifiers(() => {}, ["stop"])),
                                      "onUpdate:modelValue": $event => (toggleSelected(removeSelected.value, item.tmdbid))
                                    }, null, 8, ["model-value", "onUpdate:modelValue"])
                                  ]),
                                  _: 2
                                }, 1032, ["title", "subtitle"]))
                              }), 128))
                            ]),
                            _: 1
                          }))
                        : (_openBlock(), _createBlock(_component_VAlert, {
                            key: 3,
                            type: "success",
                            variant: "tonal",
                            density: "compact"
                          }, {
                            default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
                              _createTextVNode(" 没有需要移除的剧。 ", -1)
                            ]))]),
                            _: 1
                          }))
                    ], 64))
                  : _createCommentVNode("", true)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  disabled: importBusy.value,
                  onClick: _cache[16] || (_cache[16] = $event => (importOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[37] || (_cache[37] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }, 8, ["disabled"]),
                _createVNode(_component_VBtn, {
                  color: "primary",
                  variant: "flat",
                  loading: importBusy.value,
                  disabled: !importPreview.value,
                  onClick: applyImport
                }, {
                  default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                    _createTextVNode(" 执行导入 ", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading", "disabled"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-aab490fa"]]);

export { AppPage as default };
