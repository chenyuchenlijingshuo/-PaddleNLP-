<template>
  <div class="app-shell">
    <div class="app-background">
      <div class="app-bg-gradient"></div>
      <div class="app-orb app-orb-1"></div>
      <div class="app-orb app-orb-2"></div>
      <div class="app-orb app-orb-3"></div>
      <div class="app-orb app-orb-4"></div>
      <div class="app-particles">
        <div class="particle" v-for="i in 15" :key="i"></div>
      </div>
    </div>

    <LoginView v-if="!isAuthenticated" />

    <template v-else>
      <header class="topbar">
        <div>
          <p class="eyebrow">系统</p>
          <h1>舆情分析系统</h1>
          <p class="topbar-copy">首页总览、可视化分析、预警联动与 PaddleNLP 文本理解。</p>
        </div>
        <div class="topbar-actions">
          <div class="topbar-status">
            <span class="status-dot"></span>
            <span>已登录</span>
          </div>
          <el-button plain @click="logout">退出登录</el-button>
        </div>
      </header>

      <main class="workspace">
        <aside class="sidebar">
          <div class="sidebar-block">
            <p class="sidebar-label">导航</p>
            <button
              v-for="item in visibleTabs"
              :key="item.key"
              class="nav-button"
              :class="{ active: tab === item.key }"
              @click="tab = item.key"
            >
              <span class="nav-index">{{ item.index }}</span>
              <span>
                <strong>{{ item.label }}</strong>
                <small>{{ item.desc }}</small>
              </span>
            </button>
          </div>

          <div class="sidebar-block sidebar-summary">
            <p class="sidebar-label">当前</p>
            <strong>{{ currentTab.label }}</strong>
            <p>{{ currentTab.longDesc }}</p>
          </div>
        </aside>

        <section class="content-area">
          <div class="hero-strip">
            <div class="hero-title">
              <p class="eyebrow">模块</p>
              <h2>{{ currentTab.label }}</h2>
              <p>{{ currentTab.longDesc }}</p>
            </div>
            <div class="hero-metrics">
              <div class="metric-chip">
                <span>序号</span>
                <strong>{{ currentTab.index }}</strong>
              </div>
              <div class="metric-chip">
                <span>阶段</span>
                <strong>{{ currentTab.stage }}</strong>
              </div>
              <div class="metric-chip">
                <span>状态</span>
                <strong>可用</strong>
              </div>
            </div>
          </div>

          <transition name="panel-fade" mode="out-in">
            <HomeView v-if="tab === 'home'" key="home" @navigate="tab = $event" />
            <CollectView v-else-if="tab === 'collect'" key="collect" />
            <ProcessView v-else-if="tab === 'process'" key="process" />
            <AnalyzeView v-else-if="tab === 'analyze'" key="analyze" />
            <AlertView v-else-if="tab === 'alert'" key="alert" />
            <UsersView v-else key="users" />
          </transition>
        </section>
      </main>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AlertView from "./views/AlertView.vue";
import AnalyzeView from "./views/AnalyzeView.vue";
import CollectView from "./views/CollectView.vue";
import HomeView from "./views/HomeView.vue";
import LoginView from "./views/LoginView.vue";
import ProcessView from "./views/ProcessView.vue";
import UsersView from "./views/UsersView.vue";

const tabs = [
  { key: "home", index: "01", label: "首页", desc: "总览和入口", stage: "概览", longDesc: "查看全局态势、热点和预警提示。", roles: ["admin", "user", "viewer"] },
  { key: "collect", index: "02", label: "采集", desc: "规则和原始数据", stage: "接入", longDesc: "配置规则并执行采集。", roles: ["admin", "user"] },
  { key: "process", index: "03", label: "处理", desc: "清洗和融合", stage: "加工", longDesc: "执行预处理和融合。", roles: ["admin", "user"] },
  { key: "analyze", index: "04", label: "分析", desc: "图表与 NLP", stage: "洞察", longDesc: "查看词云、趋势、来源分布和 PaddleNLP 结果。", roles: ["admin", "user", "viewer"] },
  { key: "alert", index: "05", label: "预警", desc: "规则和日志", stage: "监控", longDesc: "查看预警规则和日志。", roles: ["admin", "user"] },
  { key: "users", index: "06", label: "用户", desc: "角色和权限", stage: "管理", longDesc: "查看用户和角色。", roles: ["admin", "user", "viewer"] },
];

const tab = ref("home");
const isAuthenticated = ref(false);
const currentUser = ref(null);

const syncAuthState = async () => {
  isAuthenticated.value = Boolean(localStorage.getItem("token"));
  if (!isAuthenticated.value) {
    tab.value = "home";
    currentUser.value = null;
    return;
  }
  
  try {
    const response = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }
    });
    const result = await response.json();
    
    if (result.code === 0 && result.data) {
      currentUser.value = result.data;
      console.log("当前用户信息:", currentUser.value);
      console.log("用户角色:", currentUser.value.role);
    } else {
      console.error("获取用户信息失败:", result);
      currentUser.value = null;
    }
  } catch (error) {
    console.error("获取用户信息异常:", error);
    currentUser.value = null;
  }
};

const visibleTabs = computed(() => {
  console.log("计算visibleTabs, currentUser:", currentUser.value);
  
  if (!currentUser.value) {
    console.log("用户未登录，显示viewer权限菜单");
    return tabs.filter(t => t.roles.includes("viewer"));
  }
  
  const userRole = currentUser.value.role;
  console.log("用户角色:", userRole);
  
  const filtered = tabs.filter(t => t.roles.includes(userRole));
  console.log("过滤后的菜单:", filtered.map(t => t.key));
  
  return filtered;
});

const canAccessTab = (tabKey) => {
  const tabConfig = tabs.find(t => t.key === tabKey);
  if (!tabConfig) return false;
  if (!currentUser.value) return tabConfig.roles.includes("viewer");
  return tabConfig.roles.includes(currentUser.value.role);
};

watch(tab, (newTab) => {
  if (!canAccessTab(newTab)) {
    tab.value = "home";
  }
});

const logout = () => {
  localStorage.removeItem("token");
  window.dispatchEvent(new Event("auth-changed"));
};

const currentTab = computed(() => tabs.find((item) => item.key === tab.value) ?? tabs[0]);

onMounted(() => {
  syncAuthState();
  window.addEventListener("auth-changed", syncAuthState);
  window.addEventListener("storage", syncAuthState);
});

onBeforeUnmount(() => {
  window.removeEventListener("auth-changed", syncAuthState);
  window.removeEventListener("storage", syncAuthState);
});
</script>
