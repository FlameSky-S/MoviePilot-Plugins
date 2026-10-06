<script setup>
/**
 * 自动续订工作台。
 * 数据全部经宿主注入的 `api` 调 `/api/v1/plugin/AutoRenew/*`。
 */
import { computed, onMounted, ref } from 'vue'
import { createAutoRenewApi } from '../api/autoRenewApi'
import { errorMessage, formatDate, seasonLabel, unwrapResponse } from '../utils/formatters'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'AutoRenew' },
  navKey: { type: String, default: 'main' },
  hideTitle: { type: Boolean, default: false },
})

const pluginBase = computed(() => `plugin/${props.pluginId || 'AutoRenew'}`)
const pluginApi = computed(() => createAutoRenewApi(props.api, pluginBase))

const SORTS = [
  { value: 'next_airing', title: 'Next Airing' },
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
const calendarEvents = ref([])

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

const activeShows = computed(() => shows.value.filter(show => !show.terminated))
const endedShows = computed(() => shows.value.filter(show => show.terminated))
/** 全局「仅提醒模式」时，单剧的续订开关没有任何作用 —— UI 要禁用而不是假装能点。 */
const reminderOnly = computed(() => !!status.value && !status.value.auto_subscribe)

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

/** 已完结区：重新拉 TMDB 元数据（万一那边又续订了，状态要能跟着变）。 */
async function refreshEnded() {
  refreshingEnded.value = true
  error.value = ''
  try {
    const res = unwrapResponse(await pluginApi.value.refresh({ scope: 'ended' }))
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

async function openCalendar() {
  calendarOpen.value = true
  try {
    const res = unwrapResponse(await pluginApi.value.calendar({ days: 60 }))
    calendarEvents.value = res?.events || []
  } catch (err) {
    error.value = errorMessage(err)
  }
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
        <VChip v-if="status" size="small" variant="tonal" prepend-icon="mdi-television">
          追踪 {{ status.tracked }} 部
        </VChip>
        <VChip v-if="status" size="small" variant="tonal" prepend-icon="mdi-clock-outline">
          {{ status.cron }}
        </VChip>
        <VChip
          v-if="status"
          size="small"
          :color="status.auto_subscribe ? 'success' : 'warning'"
          variant="tonal"
        >
          {{ status.auto_subscribe ? '自动建订阅' : '仅提醒模式' }}
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
        <VBtn
          icon="mdi-refresh"
          variant="text"
          size="small"
          :loading="loading"
          @click="load"
        />
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
                <VChip size="x-small" variant="tonal">{{ show.status_label }}</VChip>
                <VChip size="x-small" variant="tonal" color="primary">
                  {{ seasonLabel(show.season) }}
                </VChip>
              </div>
              <VChip size="x-small" variant="tonal" class="mt-1" color="secondary">
                {{ show.badge }}
              </VChip>
              <div v-if="show.next_episode_air_date" class="text-caption mt-1">
                下一集 {{ formatDate(show.next_episode_air_date) }}
              </div>
            </VCardText>
            <VCardActions class="pa-1">
              <VTooltip
                :text="
                  reminderOnly
                    ? '全局已设为「仅提醒模式」，单剧开关暂不生效'
                    : '参与自动续订：发现新季时自动建订阅'
                "
                location="top"
              >
                <template #activator="{ props: switchProps }">
                  <VSwitch
                    v-bind="switchProps"
                    :model-value="show.auto_renew"
                    :disabled="reminderOnly"
                    density="compact"
                    hide-details
                    label="续订"
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
                    size="x-small"
                    variant="text"
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
                <VChip size="x-small" variant="tonal" class="mt-1">
                  {{ show.status_label }}
                </VChip>
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
            <VFab
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

    <!-- 日历 -->
    <VDialog v-model="calendarOpen" max-width="560">
      <VCard>
        <VCardTitle class="text-subtitle-1">未来 60 天播出</VCardTitle>
        <VCardText>
          <VList v-if="calendarEvents.length" density="compact">
            <VListItem
              v-for="event in calendarEvents"
              :key="`${event.date}-${event.tmdbid}`"
              :title="event.title"
              :subtitle="`${event.date} · ${event.status_label}`"
              prepend-icon="mdi-calendar-blank"
            />
          </VList>
          <VAlert v-else type="info" variant="tonal" density="compact">
            暂无已确认的近期播出。TMDB 上未公布下一集日期的剧不会出现在这里。
          </VAlert>
        </VCardText>
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
</style>
