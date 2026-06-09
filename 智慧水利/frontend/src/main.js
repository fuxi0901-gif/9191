import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

// ECharts 按需注册
import ECharts from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const app = createApp(App)
app.component('v-chart', ECharts)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
