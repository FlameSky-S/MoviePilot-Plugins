<script setup>
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
import { computed, onMounted, ref } from 'vue'
import { createAutoRenewApi } from '../api/autoRenewApi'
import { errorMessage, unwrapResponse } from '../utils/formatters'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
})

const emit = defineEmits(['save', 'close'])

const DEFAULT_CRON = '0 */6 * * *'

const DEFAULTS = {
  enabled: false,
  auto_subscribe: true,
  notify: true,
  poll_cron: DEFAULT_CRON,
  max_actions_per_run: 5,
  show_sidebar_nav: true,
}

/** 只认这几个键，脏值一律回落默认（宿主可能传缺字段或字符串过来）。 */
function normalizeConfig(raw) {
  const source = raw && typeof raw === 'object' ? raw : {}
  const out = { ...DEFAULTS }
  for (const key of Object.keys(DEFAULTS)) {
    if (source[key] !== undefined && source[key] !== null) out[key] = source[key]
  }
  out.enabled = !!out.enabled
  out.auto_subscribe = !!out.auto_subscribe
  out.notify = !!out.notify
  out.show_sidebar_nav = !!out.show_sidebar_nav
  out.poll_cron = String(out.poll_cron || '').trim() || DEFAULT_CRON
  const limit = Number.parseInt(out.max_actions_per_run, 10)
  out.max_actions_per_run = Number.isFinite(limit) && limit > 0 ? limit : DEFAULTS.max_actions_per_run
  return out
}

const localConfig = ref({ ...DEFAULTS })
const status = ref(null)
const error = ref('')

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`)
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase))
const reminderOnly = computed(() => !localConfig.value.auto_subscribe)
const cronError = computed(() => {
  const segments = String(localConfig.value.poll_cron || '').trim().split(/\s+/).filter(Boolean)
  return segments.length === 5 ? '' : 'crontab 需要 5 段，例如 0 */6 * * *'
})

async function loadStatus() {
  try {
    status.value = unwrapResponse(await pluginApi.value.status())
  } catch (err) {
    error.value = errorMessage(err)
  }
}

function submit() {
  if (cronError.value) {
    error.value = cronError.value
    return
  }
  error.value = ''
  emit('save', {
    ...localConfig.value,
    poll_cron: String(localConfig.value.poll_cron).trim(),
    max_actions_per_run:
      Number.parseInt(localConfig.value.max_actions_per_run, 10) || DEFAULTS.max_actions_per_run,
  })
}

onMounted(() => {
  localConfig.value = normalizeConfig(props.initialConfig)
  loadStatus()
})

defineExpose({ load: loadStatus })
</script>

<template>
  <div class="autorenew-config">
    <VAlert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">
      {{ error }}
    </VAlert>

    <VCard variant="tonal" class="mb-3">
      <VCardText class="d-flex align-center flex-wrap ga-2 py-2">
        <VChip size="small" variant="tonal" prepend-icon="mdi-television">
          追踪 {{ status?.tracked ?? '—' }} 部
        </VChip>
        <VChip size="small" variant="tonal" prepend-icon="mdi-clock-outline">
          {{ status?.cron || DEFAULT_CRON }}
        </VChip>
        <VChip
          v-if="status"
          size="small"
          variant="tonal"
          :color="status.auto_subscribe ? 'success' : 'warning'"
        >
          {{ status.auto_subscribe ? '自动建订阅' : '仅提醒模式' }}
        </VChip>
        <span v-if="status?.last_run" class="text-caption">上次检测 {{ status.last_run }}</span>
      </VCardText>
    </VCard>

    <VRow dense>
      <VCol cols="12" md="4">
        <VSwitch
          v-model="localConfig.enabled"
          label="启用插件"
          density="compact"
          hide-details
          color="primary"
        />
      </VCol>
      <VCol cols="12" md="4">
        <VSwitch
          v-model="localConfig.auto_subscribe"
          label="发现新季时自动建订阅"
          density="compact"
          hide-details
          color="primary"
        />
      </VCol>
      <VCol cols="12" md="4">
        <VSwitch
          v-model="localConfig.notify"
          label="发送通知"
          density="compact"
          hide-details
          color="primary"
        />
      </VCol>
    </VRow>

    <VRow dense>
      <VCol cols="12" md="6">
        <VTextField
          v-model="localConfig.poll_cron"
          label="检测周期（crontab）"
          :error-messages="cronError"
          density="compact"
          variant="outlined"
          persistent-hint
          hint="默认 0 */6 * * *，即每 6 小时查一次 TMDB"
        />
      </VCol>
      <VCol cols="12" md="3">
        <VTextField
          v-model.number="localConfig.max_actions_per_run"
          label="每轮最多建几条订阅"
          type="number"
          min="1"
          density="compact"
          variant="outlined"
          persistent-hint
          hint="限速，防止一次对站点发起过多搜索"
        />
      </VCol>
      <VCol cols="12" md="3">
        <VSwitch
          v-model="localConfig.show_sidebar_nav"
          label="显示侧边菜单入口"
          density="compact"
          hide-details
          color="primary"
        />
      </VCol>
    </VRow>

    <VAlert
      :type="reminderOnly ? 'warning' : 'info'"
      variant="tonal"
      density="compact"
      class="mt-2"
    >
      关闭「自动建订阅」后进入<strong>仅提醒模式</strong>：仍会追踪并推送新季消息，但不会自动创建订阅。
      名单增删只影响本插件，不会动 MoviePilot 里的订阅。
    </VAlert>

    <div class="d-flex align-center mt-3 flex-wrap ga-2">
      <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save" @click="submit">
        保存
      </VBtn>
      <VSpacer />
      <VBtn variant="text" prepend-icon="mdi-refresh" @click="loadStatus">刷新状态</VBtn>
      <VBtn variant="text" prepend-icon="mdi-close" @click="emit('close')">关闭</VBtn>
    </div>
  </div>
</template>

<style scoped>
.autorenew-config {
  padding: 4px 8px 8px;
}
</style>
