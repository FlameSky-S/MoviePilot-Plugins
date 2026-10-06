import { unwrapResponse } from '../utils/formatters'

function resolvePluginBase(pluginBase) {
  const raw = typeof pluginBase === 'function' ? pluginBase() : (pluginBase?.value ?? pluginBase)
  return raw || 'plugin/AutoRenew'
}

/**
 * 宿主通过 `api` prop 注入调用器：路径是 `plugin/<PluginId><endpoint>`。
 */
export function createAutoRenewApi(api, pluginBase) {
  const get = endpoint => api.get(`${resolvePluginBase(pluginBase)}${endpoint}`)
  const post = (endpoint, payload) => api.post(`${resolvePluginBase(pluginBase)}${endpoint}`, payload)

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
      const query = new URLSearchParams(params).toString()
      return get(query ? `/calendar?${query}` : '/calendar')
    },
    check() {
      return post('/check', {})
    },
  }
}
