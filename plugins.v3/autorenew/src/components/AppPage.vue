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

const activeShows = computed(() => shows.value.filter(show => !show.terminated))
const endedShows = computed(() => shows.value.filter(show => show.terminated))

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
    await pluginApi.value.toggleShow({ tmdbid: show.tmdbid, auto_renew: !show.auto_renew })
    show.auto_renew = !show.auto_renew
    show.badge = show.auto_renew ? show.badge : '已暂停续订'
  } catch (err) {
    error.value = errorMessage(err)
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

async function importLibrary() {
  busy.value = true
  error.value = ''
  try {
    const res = unwrapResponse(await pluginApi.value.importLibrary({ only_new: true }))
    message.value = res?.message || '导入完成'
    await load()
  } catch (err) {
    error.value = errorMessage(err)
  } finally {
    busy.value = false
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
              <VSwitch
                :model-value="show.auto_renew"
                density="compact"
                hide-details
                label="续订"
                @click.stop
                @update:model-value="toggleRenew(show)"
              />
              <VSpacer />
              <VBtn
                icon="mdi-delete-outline"
                size="x-small"
                variant="text"
                @click.stop="removeShow(show)"
              />
            </VCardActions>
          </VCard>
        </VCol>
      </VRow>

      <template v-if="endedShows.length">
        <VDivider class="my-4" />
        <div class="text-subtitle-2 mb-2">已完结 / 已砍（停止轮询）</div>
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

    <!-- 右下角圆形菜单按钮 -->
    <VMenu v-model="fabOpen" location="top end" offset="16">
      <template #activator="{ props: activatorProps }">
        <VFab
          v-bind="activatorProps"
          icon="mdi-plus"
          size="large"
          color="primary"
          class="autorenew-fab"
          :loading="busy"
        />
      </template>
      <VList density="compact" min-width="200">
        <VListItem prepend-icon="mdi-magnify" title="添加剧集" @click="searchOpen = true" />
        <VListItem prepend-icon="mdi-calendar-month" title="播出日历" @click="openCalendar" />
        <VListItem prepend-icon="mdi-sync" title="立即检查" @click="runCheck" />
        <VListItem
          prepend-icon="mdi-library-shelves"
          title="从媒体库导入"
          @click="importLibrary"
        />
      </VList>
    </VMenu>

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
  </div>
</template>

<style scoped>
.autorenew-app {
  position: relative;
  min-height: 100%;
}

.autorenew-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 5;
}
</style>
