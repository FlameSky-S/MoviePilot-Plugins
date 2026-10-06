export function unwrapResponse(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'data') && response.success !== undefined) {
    return response.data
  }
  return response?.data ?? response
}

export function errorMessage(error) {
  if (!error) return ''
  if (typeof error === 'string') return error
  return error.message || error.reason || String(error)
}

export function mediaLabel(media) {
  if (!media) return ''
  return media.year ? `${media.title} (${media.year})` : `${media.title || ''}`
}

export function seasonLabel(season) {
  const number = Number(season ?? 0)
  return number > 0 ? `第 ${number} 季` : '特别季'
}

export function formatDate(value) {
  if (!value) return ''
  const text = String(value).slice(0, 10)
  return text || ''
}
