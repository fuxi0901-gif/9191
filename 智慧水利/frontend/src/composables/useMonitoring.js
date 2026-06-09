import { ref } from 'vue'
import api from '../api'

const kpiValues = ref({
  water_level: { value: '--', unit: 'm', label: '水库水位' },
  rainfall: { value: '--', unit: 'mm', label: '今日降雨量' },
  flow_rate: { value: '--', unit: 'm³/s', label: '流量' },
})

const chartData = ref({
  data_type: '',
  unit: '',
  points: [],
  loading: false,
})

async function fetchKpiValues() {
  for (const dt of ['water_level', 'rainfall', 'flow_rate']) {
    try {
      const { data } = await api.get('/monitoring/', { params: { data_type: dt, limit: 1 } })
      if (data && data.latest_value !== undefined) {
        kpiValues.value[dt].value = data.latest_value
        kpiValues.value[dt].unit = data.unit
      }
    } catch {
      // ignore
    }
  }
}

async function fetchChartData(dataType) {
  chartData.value.loading = true
  try {
    const { data } = await api.get('/monitoring/', { params: { data_type: dataType, limit: 30 } })
    chartData.value = {
      data_type: data.data_type,
      unit: data.unit,
      points: data.points || [],
      loading: false,
    }
  } catch {
    chartData.value.loading = false
  }
}

export function useMonitoring() {
  return {
    kpiValues,
    chartData,
    fetchKpiValues,
    fetchChartData,
  }
}
