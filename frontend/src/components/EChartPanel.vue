<template>
  <div ref="containerRef" class="chart-panel" :style="{ height }"></div>
</template>

<script setup>
import * as echarts from "echarts";
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  option: {
    type: Object,
    required: true,
  },
  height: {
    type: String,
    default: "320px",
  },
});

const containerRef = ref(null);
let chart;

const renderChart = async () => {
  await nextTick();
  if (!containerRef.value) return;
  if (!chart) {
    chart = echarts.init(containerRef.value);
  }
  chart.setOption(props.option, true);
};

const resizeChart = () => {
  chart?.resize();
};

onMounted(() => {
  renderChart();
  window.addEventListener("resize", resizeChart);
});

watch(() => props.option, renderChart, { deep: true });

onBeforeUnmount(() => {
  window.removeEventListener("resize", resizeChart);
  chart?.dispose();
  chart = null;
});
</script>
