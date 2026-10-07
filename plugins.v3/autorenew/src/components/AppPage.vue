<script setup>
/**
 * 自动续订工作台。
 * 数据全部经宿主注入的 `api` 调 `/api/v1/plugin/AutoRenew/*`。
 */
import { computed, onMounted, ref } from 'vue'
import { createAutoRenewApi } from '../api/autoRenewApi'
import { errorMessage, formatDate, seasonLabel, unwrapResponse } from '../utils/formatters'
// 页面内的「设置」按钮直接复用设置弹窗那个表单组件（同一份代码，不会两处漂移）
import ConfigPanel from './Config.vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
  navKey: { type: String, default: 'main' },
  hideTitle: { type: Boolean, default: false },
})

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`)
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase))

const SORTS = [
  { value: 'next_airing', title: '按播出时间' },
  { value: 'recent', title: '最近添加' },
]

const loading = ref(false)
const busy = ref(false)
const message = ref('')
const error = ref('')
const shows = ref([])
const status = ref(null)
const sort = ref('next_airing')
const fabOpen = ref(false)

const searchOpen = ref(false)
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)

const calendarOpen = ref(false)
const calendarGrid = ref(null)
const calendarUpcoming = ref([])
const calendarUpcomingTotal = ref(0)
const calendarLoading = ref(false)
const CAL_MAX_PER_DAY = 4

const detailOpen = ref(false)
const detail = ref(null)

// 「从媒体库导入」确认流程
const importOpen = ref(false)
const importPreview = ref(null)
const importSync = ref(false)
const importBusy = ref(false)
const addSelected = ref([])
const removeSelected = ref([])

const refreshingEnded = ref(false)

// 页面内「设置」：直接渲染 Config.vue（与插件列表里的设置弹窗同一份表单）
const settingsOpen = ref(false)
const settingsConfig = ref(null)
const settingsLoading = ref(false)

const activeShows = computed(() => shows.value.filter(show => !show.terminated))
const endedShows = computed(() => shows.value.filter(show => show.terminated))
/** 全局「仅提醒模式」时，单剧的续订开关没有任何作用 —— UI 要禁用而不是假装能点。 */
const reminderOnly = computed(() => !!status.value && !status.value.auto_subscribe)

/** cron 的自然语言说明由后端算好（这样它能进单测），前端只负责展示。 */
const cronTooltip = computed(() => {
  if (!status.value) return ''
  const text = String(status.value.cron_text || '').trim()
  const expr = status.value.cron
  if (!text) return `检测周期（crontab）：${expr}`
  if (text.startsWith('分钟 ')) return `检测周期：${text}（未识别的写法，按字段直译）`
  return `检测周期：${text}（crontab：${expr}）`
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [list, info] = await Promise.all([
      pluginApi.value.shows(sort.value),
      pluginApi.value.status(),
    ])
    shows.value = unwrapResponse(list) || []
    status.value = unwrapResponse(info)
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    loading.value = false
  }
}

async function changeSort() {
  await load()
}

/** 打开页面内设置弹窗：先取回当前配置再挂载表单（表单在 onMounted 里读 initial-config）。 */
async function openSettings() {
  settingsLoading.value = true
  error.value = ''
  try {
    settingsConfig.value = unwrapResponse(await pluginApi.value.config()) || {}
    settingsOpen.value = true
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    settingsLoading.value = false
  }
}

/** 保存：后端 update_config + init_plugin 立即生效，不需要宿主重载。 */
async function saveSettings(payload) {
  try {
    const res = unwrapResponse(await pluginApi.value.saveConfig(payload))
    settingsOpen.value = false
    settingsConfig.value = null
    message.value = res?.message || '设置已保存并生效'
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  }
}

async function toggleRenew(show) {
  try {
    const res = unwrapResponse(
      await pluginApi.value.toggleShow({ tmdbid: show.tmdbid, auto_renew: !show.auto_renew }),
    )
    if (res?.auto_renew !== undefined) show.auto_renew = res.auto_renew
    await load() // 徽标与排序会随开关变化，整体重载最稳
  } catch (err) {
    error.value = errorMessage(err)
  }
}

/** 已完结区：重新拉 TMDB 元数据，并先强制同步一次宿主媒体库。
 *
 *  为什么必须带 sync：卡片的「x/y 季」里 x 来自宿主的 mediaserveritem **缓存**，
 *  那份缓存每 6h 才更新一次 —— 刚下载入库的剧会一直显示旧数字。
 *  同步完再读，数字才是当下真实的。
 */
async function refreshEnded() {
  refreshingEnded.value = true
  error.value = ''
  try {
    const res = unwrapResponse(await pluginApi.value.refresh({ scope: 'ended', sync: true }))
    message.value = res?.message || '已刷新'
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    refreshingEnded.value = false
  }
}

async function removeShow(show) {
  try {
    const res = unwrapResponse(await pluginApi.value.removeShow({ tmdbid: show.tmdbid }))
    message.value = res?.message || '已移出追踪名单'
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  }
}

async function openDetail(show) {
  detail.value = { ...show, seasons: [] }
  detailOpen.value = true
  try {
    const res = unwrapResponse(
      await pluginApi.value.showSeasons(new URLSearchParams({ tmdbid: show.tmdbid })),
    )
    detail.value = { ...show, ...(res || {}) }
  } catch (err) {
    error.value = errorMessage(err)
  }
}

async function runSearch() {
  if (!searchKeyword.value.trim()) return
  searching.value = true
  error.value = ''
  try {
    const res = await pluginApi.value.search(
      new URLSearchParams({ keyword: searchKeyword.value.trim() }),
    )
    searchResults.value = unwrapResponse(res) || []
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    searching.value = false
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
    )
    message.value = res?.message || '已加入追踪'
    item.tracked = true
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  }
}

/** 打开确认弹窗：先比对一次，默认全勾。 */
async function openImport() {
  importOpen.value = true
  importSync.value = false
  await loadImportPreview()
}

/**
 * 比对。「先强制同步媒体库再比对」打开时会调宿主 `MediaServerChain.sync`
 * 跑一遍全库同步（较慢），换来「库里已删除的剧」也能被立刻识别出来。
 */
async function loadImportPreview() {
  importBusy.value = true
  error.value = ''
  try {
    const res = unwrapResponse(await pluginApi.value.importPreview({ sync: importSync.value }))
    importPreview.value = res
    addSelected.value = (res?.added || []).map(item => item.tmdbid)
    removeSelected.value = (res?.removed || []).map(item => item.tmdbid)
    if (res?.sync_note) message.value = res.sync_note
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    importBusy.value = false
  }
}

function toggleSelected(listRef, tmdbid) {
  const index = listRef.value.indexOf(tmdbid)
  if (index >= 0) listRef.value.splice(index, 1)
  else listRef.value.push(tmdbid)
}

async function applyImport() {
  importBusy.value = true
  error.value = ''
  try {
    const res = unwrapResponse(
      await pluginApi.value.importApply({ add: addSelected.value, remove: removeSelected.value }),
    )
    message.value = res?.message || '导入完成'
    importOpen.value = false
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    importBusy.value = false
  }
}

async function runCheck() {
  busy.value = true
  error.value = ''
  try {
    const res = unwrapResponse(await pluginApi.value.check())
    const result = res?.result || {}
    message.value = `检测完成：检查 ${result.checked ?? 0} 部，新建订阅 ${(result.renewed || []).length} 条`
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = false
  }
}

/** 拉某个月的月历网格；month 为空则回落到本月。 */
async function loadCalendar(month = '') {
  calendarLoading.value = true
  error.value = ''
  try {
    const res = unwrapResponse(await pluginApi.value.calendar({ month }))
    calendarGrid.value = res?.grid || null
    calendarUpcoming.value = res?.upcoming || []
    calendarUpcomingTotal.value = res?.upcoming_total || 0
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    calendarLoading.value = false
  }
}

async function openCalendar() {
  calendarOpen.value = true
  await loadCalendar('')
}

function shiftCalendar(step) {
  const grid = calendarGrid.value
  if (!grid) return
  loadCalendar(step < 0 ? grid.prev : grid.next)
}

function visibleEvents(cell) {
  return (cell.events || []).slice(0, CAL_MAX_PER_DAY)
}

/** 日历事件的 hover 提示：剧名 · 集号 · 状态 + 集标题（有就列出来）。 */
function calendarEventTitle(event) {
  const label = event.label || `S${event.season}`
  const head = `${event.title} · ${label} · ${event.status_label}`
  const names = (event.episode_names || []).filter(Boolean)
  if (!names.length) return head
  return `${head}\n${names.join(' / ')}`
}

function openCalendarEvent(event) {
  const show = shows.value.find(item => item.tmdbid === event.tmdbid)
  calendarOpen.value = false
  if (show) openDetail(show)
}

const calendarTitle = computed(() => {
  const grid = calendarGrid.value
  return grid ? `${grid.year} 年 ${grid.month} 月` : '播出日历'
})

/** 徽标配色：让「有活儿要干」的比「没事干」的显眼。 */
function badgeColor(badge) {
  if (badge === '有新季可订阅') return 'secondary'
  if (badge === '新季已确认待开播') return 'info'
  if (badge === '已追平') return 'success'
  if (badge === '已暂停续订') return 'warning'
  return ''
}

/** 已完结区「x/y 季」的配色：季齐了=绿，缺季=橙（缺的才值得你去补）。 */
function seasonProgressColor(show) {
  const total = Number(show?.total_seasons || 0)
  const have = Number(show?.library_seasons || 0)
  if (!total) return undefined
  return have >= total ? 'success' : 'warning'
}

onMounted(load)

defineExpose({ load, loading })
</script>

<template>
  <div class="autorenew-app">
    <VContainer fluid class="pa-3">
      <VAlert
        v-if="error"
        type="error"
        variant="tonal"
        density="compact"
        closable
        class="mb-3"
        @click:close="error = ''"
      >
        {{ error }}
      </VAlert>
      <VAlert
        v-if="message"
        type="success"
        variant="tonal"
        density="compact"
        closable
        class="mb-3"
        @click:close="message = ''"
      >
        {{ message }}
      </VAlert>

      <div class="d-flex align-center flex-wrap ga-2 mb-3">
        <!-- 「追踪 X 部」只算正在追踪的（不含已完结/已砍区），与下方卡片数一致 -->
        <VChip v-if="status" size="small" variant="tonal" prepend-icon="mdi-television">
          追踪 {{ status.tracking ?? status.tracked }} 部
        </VChip>
        <VChip
          v-if="status"
          size="small"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-autorenew"
        >
          自动续订 {{ status.auto_renew_on ?? 0 }} 部
        </VChip>
        <VTooltip v-if="status" :text="cronTooltip" location="bottom" max-width="360">
          <template #activator="{ props: cronProps }">
            <VChip
              v-bind="cronProps"
              size="small"
              variant="tonal"
              prepend-icon="mdi-clock-outline"
            >
              {{ status.cron }}
            </VChip>
          </template>
        </VTooltip>
        <VChip
          v-if="status"
          size="small"
          :color="status.auto_subscribe ? 'success' : 'warning'"
          variant="tonal"
        >
          {{ status.auto_subscribe ? '自动续订已开启' : '仅提醒模式' }}
        </VChip>
        <VSpacer />
        <VSelect
          v-model="sort"
          :items="SORTS"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 180px"
          @update:model-value="changeSort"
        />
        <VTooltip
          text="重新读取追踪名单与插件状态（只读，不访问 TMDB）"
          location="bottom"
          max-width="320"
        >
          <template #activator="{ props: reloadProps }">
            <VBtn
              v-bind="reloadProps"
              icon="mdi-refresh"
              variant="text"
              size="small"
              :loading="loading"
              @click="load"
            />
          </template>
        </VTooltip>
        <VTooltip
          text="打开插件设置：续订规则、检测周期、通知开关"
          location="bottom"
          max-width="320"
        >
          <template #activator="{ props: settingsProps }">
            <VBtn
              v-bind="settingsProps"
              icon="mdi-cog-outline"
              variant="text"
              size="small"
              :loading="settingsLoading"
              @click="openSettings"
            />
          </template>
        </VTooltip>
      </div>

      <VAlert v-if="!loading && !shows.length" type="info" variant="tonal">
        追踪名单还是空的。点右下角按钮「从媒体库导入」，或「添加剧集」搜索 TMDB。
      </VAlert>

      <VRow dense>
        <VCol
          v-for="show in activeShows"
          :key="show.tmdbid"
          cols="6"
          sm="4"
          md="3"
          lg="2"
        >
          <VCard class="h-100" variant="flat" @click="openDetail(show)">
            <VImg
              :src="show.poster_url || ''"
              aspect-ratio="0.68"
              cover
              class="bg-grey-darken-3"
            >
              <template #placeholder>
                <div class="d-flex align-center justify-center fill-height">
                  <VIcon icon="mdi-television" size="48" />
                </div>
              </template>
            </VImg>
            <VCardText class="pa-2">
              <div class="text-body-2 font-weight-medium text-truncate">
                {{ show.title }}
              </div>
              <div class="d-flex align-center flex-wrap ga-1 mt-1">
                <VChip
                  size="x-small"
                  variant="tonal"
                  :title="show.tmdb_status ? `TMDB 状态：${show.tmdb_status}` : ''"
                >
                  {{ show.status_label }}
                </VChip>
                <VChip size="x-small" variant="tonal" color="primary">
                  {{ seasonLabel(show.season) }}
                </VChip>
                <VChip
                  v-if="show.badge"
                  size="x-small"
                  variant="tonal"
                  :color="badgeColor(show.badge)"
                >
                  {{ show.badge }}
                </VChip>
              </div>
              <div v-if="show.next_episode_air_date" class="text-caption mt-1">
                下一集 {{ formatDate(show.next_episode_air_date) }}
              </div>
            </VCardText>
            <VDivider />
            <VCardActions class="px-2 py-1 flex-nowrap">
              <VTooltip
                :text="
                  reminderOnly
                    ? '全局已设为「仅提醒模式」，单剧开关暂不生效'
                    : '参与自动续订：发现新季时自动建订阅'
                "
                location="top"
              >
                <template #activator="{ props: switchProps }">
                  <!--
                    ms-1（+4px）：VSwitch 渲染出的轨道左缘比控件框靠左 4px，而
                    控件框本身又在卡片左内边距上 —— 实测轨道会比上方文字列偏左
                    12px。+4px 后轨道左缘正好落在文字列的左缘上。
                    （别用 ms-n2：那是往左推，会偏得更狠。）
                  -->
                  <VSwitch
                    v-bind="switchProps"
                    :model-value="show.auto_renew"
                    :disabled="reminderOnly"
                    density="compact"
                    hide-details
                    label="续订"
                    class="ms-1"
                    @click.stop
                    @update:model-value="toggleRenew(show)"
                  />
                </template>
              </VTooltip>
              <VSpacer />
              <VTooltip text="移出追踪名单（不影响 MoviePilot 里的订阅）" location="top">
                <template #activator="{ props: deleteProps }">
                  <VBtn
                    v-bind="deleteProps"
                    icon="mdi-delete-outline"
                    size="small"
                    variant="text"
                    color="error"
                    @click.stop="removeShow(show)"
                  />
                </template>
              </VTooltip>
            </VCardActions>
          </VCard>
        </VCol>
      </VRow>

      <template v-if="endedShows.length">
        <VDivider class="my-4" />
        <div class="d-flex align-center flex-wrap ga-2 mb-2">
          <span class="text-subtitle-2">
            已完结 / 已砍（停止轮询）· {{ endedShows.length }} 部
          </span>
          <VSpacer />
          <VTooltip text="重新向 TMDB 拉取这些剧的状态与季信息" location="top">
            <template #activator="{ props: refreshProps }">
              <VBtn
                v-bind="refreshProps"
                size="small"
                variant="text"
                prepend-icon="mdi-refresh"
                :loading="refreshingEnded"
                @click.stop="refreshEnded"
              >
                刷新 TMDB 信息
              </VBtn>
            </template>
          </VTooltip>
        </div>
        <VRow dense>
          <VCol v-for="show in endedShows" :key="show.tmdbid" cols="6" sm="4" md="3" lg="2">
            <VCard class="h-100" variant="tonal" style="opacity: 0.6" @click="openDetail(show)">
              <VCardText class="pa-2">
                <div class="text-body-2 text-truncate">{{ show.title }}</div>
                <div class="d-flex align-center flex-wrap ga-1 mt-1">
                  <VChip
                    size="x-small"
                    variant="tonal"
                    :title="show.tmdb_status ? `TMDB 状态：${show.tmdb_status}` : ''"
                  >
                    {{ show.status_label }}
                  </VChip>
                  <!-- x = 磁盘上有的季数，y = 总季数（都不含特别季 S0） -->
                  <VChip
                    v-if="show.total_seasons"
                    size="x-small"
                    variant="tonal"
                    :color="seasonProgressColor(show)"
                  >
                    {{ show.library_seasons }}/{{ show.total_seasons }} 季
                  </VChip>
                </div>
              </VCardText>
            </VCard>
          </VCol>
        </VRow>
      </template>
    </VContainer>

    <!--
      右下角悬浮圆形菜单按钮。
      用 Teleport 挂到 body：联邦组件若挂在一个带 transform 的容器里，
      `position: fixed` 会相对那个容器定位而不是视口 —— 这就是「按钮有一半在屏幕外」
      的成因（实测症状）。挂到 body 之后，视口才是包含块。
    -->
    <Teleport to="body">
      <div class="autorenew-fab-host">
        <VMenu v-model="fabOpen" location="top end" offset="16">
          <template #activator="{ props: activatorProps }">
            <!--
              这里用 VBtn 而**不是** VFab：VFab 渲染出的 .v-fab 包裹层是 inline-flex
              且宽高为 0（浏览器实测 getBoundingClientRect() = 0×0），它的
              .v-fab__container 又是 position:absolute —— 尺寸塌成 0 之后按钮会飘到
              视口右缘被裁掉（「有一半在屏幕外」）。VBtn 有固有尺寸，放进这个 fixed
              宿主里位置就是对的。
            -->
            <VBtn
              v-bind="activatorProps"
              icon="mdi-dots-grid"
              size="large"
              color="primary"
              elevation="8"
              :loading="busy"
            />
          </template>
          <VList density="compact" min-width="200">
            <VListItem prepend-icon="mdi-magnify" title="添加剧集" @click="searchOpen = true" />
            <VListItem prepend-icon="mdi-calendar-month" title="播出日历" @click="openCalendar" />
            <VListItem prepend-icon="mdi-sync" title="立即检查" @click="runCheck" />
            <VListItem
              prepend-icon="mdi-library-shelves"
              title="从媒体库导入…"
              @click="openImport"
            />
          </VList>
        </VMenu>
      </div>
    </Teleport>

    <!-- 页面内「设置」：复用 Config.vue（与插件列表里的设置弹窗同一份表单） -->
    <VDialog v-model="settingsOpen" max-width="760" scrollable>
      <VCard>
        <VCardItem class="py-2">
          <template #title>
            <span class="text-subtitle-1">自动续订 · 设置</span>
          </template>
          <template #append>
            <VBtn icon="mdi-close" variant="text" size="small" @click="settingsOpen = false" />
          </template>
        </VCardItem>
        <VDivider />
        <VCardText class="pa-4">
          <ConfigPanel
            v-if="settingsOpen && settingsConfig"
            :initial-config="settingsConfig"
            :api="props.api"
            :plugin-id="props.pluginId"
            @save="saveSettings"
            @close="settingsOpen = false"
          />
        </VCardText>
      </VCard>
    </VDialog>

    <!-- 搜索 / 添加 -->
    <VDialog v-model="searchOpen" max-width="720">
      <VCard>
        <VCardTitle class="text-subtitle-1">添加剧集</VCardTitle>
        <VCardText>
          <VTextField
            v-model="searchKeyword"
            label="剧名"
            density="compact"
            variant="outlined"
            hide-details
            append-inner-icon="mdi-magnify"
            @keyup.enter="runSearch"
            @click:append-inner="runSearch"
          />
          <VProgressLinear v-if="searching" indeterminate class="mt-2" />
          <VList v-if="searchResults.length" density="compact" class="mt-2">
            <VListItem v-for="item in searchResults" :key="item.tmdbid">
              <template #prepend>
                <VAvatar rounded size="40">
                  <VImg :src="item.poster_url || ''" />
                </VAvatar>
              </template>
              <VListItemTitle class="text-body-2">{{ item.title }}</VListItemTitle>
              <VListItemSubtitle class="text-caption">
                {{ item.year || '年份未知' }}
              </VListItemSubtitle>
              <template #append>
                <VChip v-if="item.tracked" size="small" variant="tonal">已追踪</VChip>
                <VBtn v-else size="small" variant="text" @click="addShow(item, 1)">加入</VBtn>
              </template>
            </VListItem>
          </VList>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="searchOpen = false">关闭</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- 季进度 -->
    <VDialog v-model="detailOpen" max-width="640">
      <VCard>
        <VCardTitle class="text-subtitle-1">
          {{ detail?.title }} · {{ seasonLabel(detail?.tracked_season || 0) }}已追踪
        </VCardTitle>
        <VCardText>
          <VTable density="compact">
            <thead>
              <tr>
                <th>季</th>
                <th>TMDB 集数</th>
                <th>库内集数</th>
                <th>状态</th>
                <th>首播</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="season in detail?.seasons || []" :key="season.season_number">
                <td>{{ season.season_number }}</td>
                <td>{{ season.episode_count }}</td>
                <td>{{ season.in_library }}</td>
                <td>
                  <VChip size="x-small" variant="tonal" :color="season.tracked ? 'primary' : ''">
                    {{ season.state }}
                  </VChip>
                </td>
                <td>{{ formatDate(season.air_date) || '—' }}</td>
              </tr>
            </tbody>
          </VTable>
          <VAlert v-if="!detail?.seasons?.length" type="info" variant="tonal" density="compact">
            未取到季信息。
          </VAlert>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="detailOpen = false">关闭</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- 播出日历：周一起始的月历网格（Sonarr 式），事件精确到集 -->
    <VDialog v-model="calendarOpen" max-width="1560" scrollable>
      <VCard>
        <VCardItem class="py-2">
          <template #title>
            <span class="text-subtitle-1">播出日历</span>
          </template>
          <template #append>
            <div class="d-flex align-center ga-1">
              <VBtn
                icon="mdi-chevron-left"
                variant="text"
                size="small"
                @click="shiftCalendar(-1)"
              />
              <div class="autorenew-cal-title">{{ calendarTitle }}</div>
              <VBtn
                icon="mdi-chevron-right"
                variant="text"
                size="small"
                @click="shiftCalendar(1)"
              />
              <VBtn size="small" variant="tonal" class="ms-2" @click="loadCalendar('')">
                今天
              </VBtn>
            </div>
          </template>
        </VCardItem>
        <VDivider />

        <VCardText class="pa-3">
          <VProgressLinear v-if="calendarLoading" indeterminate class="mb-2" />

          <div class="autorenew-cal-weekdays">
            <div
              v-for="(label, index) in calendarGrid?.weekday_headers || []"
              :key="label"
              class="autorenew-cal-weekday"
              :class="{ 'is-weekend': index >= 5 }"
            >
              {{ label }}
            </div>
          </div>

          <div
            v-for="(week, wi) in calendarGrid?.weeks || []"
            :key="wi"
            class="autorenew-cal-week"
          >
            <div
              v-for="cell in week"
              :key="cell.date"
              class="autorenew-cal-cell"
              :class="{
                'is-out': !cell.in_month,
                'is-today': cell.is_today,
                'has-events': cell.events.length,
              }"
            >
              <div class="autorenew-cal-daynum">
                <span v-if="cell.is_today" class="autorenew-cal-todaynum">{{ cell.day }}</span>
                <span v-else>{{ cell.day }}</span>
              </div>
              <div class="autorenew-cal-events">
                <div
                  v-for="event in visibleEvents(cell)"
                  :key="`${cell.date}-${event.tmdbid}-${event.episode_start}`"
                  class="autorenew-cal-event"
                  :title="calendarEventTitle(event)"
                  @click="openCalendarEvent(event)"
                >
                  <VImg
                    :src="event.poster_url || ''"
                    width="24"
                    height="36"
                    cover
                    class="autorenew-cal-poster bg-grey-darken-3"
                  />
                  <div class="autorenew-cal-eventtext">
                    <div class="autorenew-cal-eventtitle">{{ event.title }}</div>
                    <div class="autorenew-cal-eventmeta">{{ event.label || `S${event.season}` }}</div>
                  </div>
                </div>
                <div v-if="cell.events.length > CAL_MAX_PER_DAY" class="autorenew-cal-more">
                  +{{ cell.events.length - CAL_MAX_PER_DAY }} 条
                </div>
              </div>
            </div>
          </div>

          <div v-if="!calendarLoading && !calendarGrid?.events_total" class="text-caption text-medium-emphasis mt-2">
            本月没有已确认的播出。TMDB 尚未公布下一集日期的剧不会出现在这里；可以用左右箭头查看其它月份。
          </div>
        </VCardText>

        <template v-if="calendarUpcoming.length">
          <VDivider />
          <VCardText class="pa-3">
            <div class="text-caption text-medium-emphasis mb-2">
              接下来（共 {{ calendarUpcomingTotal }} 集）
            </div>
            <div class="d-flex flex-wrap ga-2">
              <div
                v-for="event in calendarUpcoming"
                :key="`up-${event.date}-${event.tmdbid}-${event.episode_start}`"
                class="autorenew-cal-upcoming"
                @click="openCalendarEvent(event)"
              >
                <VImg
                  :src="event.poster_url || ''"
                  width="28"
                  height="42"
                  cover
                  class="autorenew-cal-poster bg-grey-darken-3"
                />
                <div class="autorenew-cal-eventtext">
                  <div class="autorenew-cal-eventtitle">{{ event.title }}</div>
                  <div class="autorenew-cal-eventmeta">
                    {{ formatDate(event.date) }} · {{ event.label || `S${event.season}` }}
                  </div>
                </div>
              </div>
            </div>
          </VCardText>
        </template>

        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="calendarOpen = false">关闭</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <!-- 从媒体库导入：先比对、逐条确认，再执行 -->
    <VDialog v-model="importOpen" max-width="720" scrollable>
      <VCard>
        <VCardTitle class="text-subtitle-1">从媒体库导入</VCardTitle>
        <VCardText>
          <VAlert type="info" variant="tonal" density="compact" class="mb-3">
            只影响本插件的追踪名单，<strong>不会创建任何 MoviePilot 订阅</strong>。
          </VAlert>

          <VSwitch
            v-model="importSync"
            label="先强制同步媒体库再比对"
            density="compact"
            hide-details
            color="primary"
            :disabled="importBusy"
            @update:model-value="loadImportPreview"
          />
          <div class="text-caption text-medium-emphasis mb-3">
            宿主每 6 小时自动同步一次媒体库；打开这项会立刻跑一遍全库同步（较慢），
            这样「已从库里删除的剧」也能马上被识别出来。
            <template v-if="importPreview?.last_sync">
              <br />当前缓存最近更新：{{ importPreview.last_sync }}
            </template>
          </div>

          <VProgressLinear v-if="importBusy" indeterminate class="mb-3" />

          <template v-if="importPreview">
            <div class="text-subtitle-2 mb-1">
              将新增 {{ importPreview.added.length }} 部
              <span class="text-caption text-medium-emphasis">
                （库内共 {{ importPreview.library_total }} 部，名单内已有 {{ importPreview.kept }} 部）
              </span>
            </div>
            <VList v-if="importPreview.added.length" density="compact" class="mb-3">
              <VListItem
                v-for="item in importPreview.added"
                :key="`add-${item.tmdbid}`"
                :title="item.title"
                :subtitle="`TMDB ${item.tmdbid} · 库内最高第 ${item.season} 季`"
              >
                <template #prepend>
                  <VCheckbox
                    :model-value="addSelected.includes(item.tmdbid)"
                    density="compact"
                    hide-details
                    color="primary"
                    @click.stop
                    @update:model-value="toggleSelected(addSelected, item.tmdbid)"
                  />
                </template>
              </VListItem>
            </VList>
            <VAlert v-else type="success" variant="tonal" density="compact" class="mb-3">
              没有需要新增的剧。
            </VAlert>

            <div class="text-subtitle-2 mb-1">将移除 {{ importPreview.removed.length }} 部</div>
            <div class="text-caption text-medium-emphasis mb-2">
              只列出「来源 = 媒体库导入」且现在库里已找不到的剧；手动添加、订阅同步进来的永不在此列。
            </div>
            <VList v-if="importPreview.removed.length" density="compact">
              <VListItem
                v-for="item in importPreview.removed"
                :key="`del-${item.tmdbid}`"
                :title="item.title"
                :subtitle="`TMDB ${item.tmdbid} · 媒体库里已找不到`"
              >
                <template #prepend>
                  <VCheckbox
                    :model-value="removeSelected.includes(item.tmdbid)"
                    density="compact"
                    hide-details
                    color="error"
                    @click.stop
                    @update:model-value="toggleSelected(removeSelected, item.tmdbid)"
                  />
                </template>
              </VListItem>
            </VList>
            <VAlert v-else type="success" variant="tonal" density="compact">
              没有需要移除的剧。
            </VAlert>
          </template>
        </VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="importBusy" @click="importOpen = false">取消</VBtn>
          <VBtn
            color="primary"
            variant="flat"
            :loading="importBusy"
            :disabled="!importPreview"
            @click="applyImport"
          >
            执行导入
          </VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.autorenew-app {
  position: relative;
  min-height: 100%;
}

/* Teleport 到 body 后的锚点：钉在视口右下角；z-index 低于对话框（~2400）*/
.autorenew-fab-host {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2000;
}

/* ---------------- 播出日历：月历网格 ---------------- */
.autorenew-cal-title {
  min-width: 104px;
  text-align: center;
  font-weight: 600;
  font-size: 0.9rem;
}

.autorenew-cal-weekdays,
.autorenew-cal-week {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 4px;
}

.autorenew-cal-weekdays {
  margin-bottom: 4px;
}

.autorenew-cal-week {
  margin-bottom: 6px;
}

.autorenew-cal-weekday {
  text-align: center;
  font-size: 0.84rem;
  letter-spacing: 0.08em;
  padding: 4px 0;
  opacity: 0.65;
}

.autorenew-cal-weekday.is-weekend {
  color: rgb(var(--v-theme-secondary));
  opacity: 0.9;
}

.autorenew-cal-cell {
  min-height: 124px;
  padding: 6px 7px 7px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
  background: rgba(var(--v-theme-surface), 0.35);
}

.autorenew-cal-cell.is-out {
  opacity: 0.34;
}

.autorenew-cal-cell.has-events {
  background: rgba(var(--v-theme-primary), 0.06);
}

.autorenew-cal-cell.is-today {
  border-color: rgb(var(--v-theme-primary));
  box-shadow: inset 0 0 0 1px rgb(var(--v-theme-primary));
}

.autorenew-cal-daynum {
  font-size: 0.86rem;
  line-height: 1.2;
  text-align: right;
  opacity: 0.85;
}

.autorenew-cal-todaynum {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 23px;
  height: 23px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
  font-weight: 700;
}

.autorenew-cal-events {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow: hidden;
  min-height: 0;
}

.autorenew-cal-event {
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 2px 3px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.autorenew-cal-event:hover {
  background: rgba(var(--v-theme-primary), 0.18);
}

.autorenew-cal-poster {
  flex: none;
  border-radius: 3px;
}

.autorenew-cal-eventtext {
  min-width: 0;
}

.autorenew-cal-eventtitle {
  font-size: 0.8rem;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.autorenew-cal-eventmeta {
  font-size: 0.72rem;
  line-height: 1.15;
  opacity: 0.68;
  font-variant-numeric: tabular-nums;
}

.autorenew-cal-more {
  font-size: 0.72rem;
  opacity: 0.62;
  padding-left: 3px;
}

.autorenew-cal-upcoming {
  display: flex;
  gap: 7px;
  align-items: center;
  max-width: 300px;
  padding: 5px 10px 5px 5px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
}

.autorenew-cal-upcoming:hover {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}
</style>
