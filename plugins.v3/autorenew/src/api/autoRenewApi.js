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
  const query = params => {
    const search = new URLSearchParams(params || {}).toString()
    return search ? `?${search}` : ''
  }

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
    check() {
      return post('/check', {})
    },
  }
}
