<script setup>
/**
 * 插件设置页的 Vue 视图。
 * 宿主默认仍会渲染后端 `get_form()` 构建的原生表单；此组件作为补充视图，
 * 展示本插件的运行状态（只读），避免与原生表单字段产生歧义。
 */
import { computed, onMounted, ref } from 'vue'
import { createAutoRenewApi } from '../api/autoRenewApi'
import { errorMessage, unwrapResponse } from '../utils/formatters'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
})

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`)
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase))

const status = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    status.value = unwrapResponse(await pluginApi.value.status())
  } catch (err) {
    error.value = errorMessage(err)
  }
}

onMounted(load)

defineExpose({ load })
</script>

<template>
  <VCard variant="tonal" class="ma-2">
    <VCardTitle class="text-subtitle-1">自动续订 · 运行状态</VCardTitle>
    <VCardText>
      <VAlert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
        {{ error }}
      </VAlert>
      <VList v-if="status" density="compact">
        <VListItem title="插件状态" :subtitle="status.enabled ? '已启用' : '已停用'" />
        <VListItem title="追踪中" :subtitle="`${status.tracked} 部`" />
        <VListItem title="自动建订阅" :subtitle="status.auto_subscribe ? '开' : '仅提醒模式'" />
        <VListItem title="检测周期" :subtitle="status.cron" />
        <VListItem title="上次检测" :subtitle="status.last_run || '尚未执行'" />
      </VList>
      <VAlert v-else type="info" variant="tonal" density="compact">加载中…</VAlert>
    </VCardText>
    <VCardActions>
      <VBtn variant="text" prepend-icon="mdi-refresh" @click="load">刷新</VBtn>
    </VCardActions>
  </VCard>
</template>
