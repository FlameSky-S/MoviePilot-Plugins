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

export { _export_sfc as _, createAutoRenewApi as c, errorMessage as e, formatDate as f, seasonLabel as s, unwrapResponse as u };
