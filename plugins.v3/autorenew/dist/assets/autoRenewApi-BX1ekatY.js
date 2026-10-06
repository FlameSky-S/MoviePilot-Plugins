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
    importLibrary(payload = {}) {
      return post('/import_library', payload)
    },
    calendar(params = {}) {
      const query = new URLSearchParams(params).toString();
      return get(query ? `/calendar?${query}` : '/calendar')
    },
    check() {
      return post('/check', {})
    },
  }
}

export { createAutoRenewApi as c, errorMessage as e, formatDate as f, seasonLabel as s, unwrapResponse as u };
