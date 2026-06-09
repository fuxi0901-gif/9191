<template>
  <div class="monitoring-chart">
    <div class="chart-header">
      <span class="chart-title">{{ title }}</span>
      <el-select v-model="selectedType" @change="onTypeChange" size="small" style="width: 140px">
        <el-option label="水库水位" value="water_level" />
        <el-option label="降雨量" value="rainfall" />
        <el-option label="流量" value="flow_rate" />
      </el-select>
    </div>
    <div class="chart-body" v-loading="chartData.loading">
      <v-chart v-if="chartData.points.length > 0 && !chartData.loading" :option="chartOption" autoresize style="height: 220px" />
      <div v-else-if="!chartData.loading" class="chart-empty">暂无监测数据</div>
    </div>
    <div v-if="latestStr" class="chart-latest">
      最新值：<strong>{{ latestStr }}</strong>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useMonitoring } from '../composables/useMonitoring'

const { chartData, fetchChartData } = useMonitoring()

const selectedType = ref('water_level')
const title = computed(() => {
  const labels = { water_level: '水库水位趋势', rainfall: '降雨量趋势', flow_rate: '流量趋势' }
  return labels[selectedType.value] || ''
})

const latestStr = computed(() => {
  if (!chartData.value.points.length) return ''
  const p = chartData.value.points[chartData.value.points.length - 1]
  return `${p.value} ${p.unit || chartData.value.unit || ''}`
})

const chartOption = computed(() => {
  const points = chartData.value.points
  if (!points.length) return {}
  return {
    grid: { top: 30, right: 20, bottom: 30, left: 50 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: points.map(p => p.timestamp.slice(5, 10)),
      axisLabel: { fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      name: chartData.value.unit || '',
      axisLabel: { fontSize: 10 },
    },
    series: [
      selectedType.value === 'rainfall'
        ? {
            type: 'bar',
            data: points.map(p => p.value),
            itemStyle: { color: '#409EFF', borderRadius: [4, 4, 0, 0] },
            barMaxWidth: 12,
          }
        : {
            type: 'line',
            data: points.map(p => p.value),
            smooth: true,
            lineStyle: { color: '#27ae60', width: 2 },
            itemStyle: { color: '#27ae60' },
            areaStyle: { color: 'rgba(39, 174, 96, 0.1)' },
          },
    ],
  }
})

function onTypeChange() {
  fetchChartData(selectedType.value)
}

onMounted(() => {
  fetchChartData('water_level')
})
</script>

<style scoped>
.monitoring-chart {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  padding: 16px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.chart-body {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-empty {
  color: #ccc;
  font-size: 14px;
}

.chart-latest {
  text-align: right;
  font-size: 12px;
  color: #888;
  margin-top: 8px;
}
</style>
