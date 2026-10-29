<template>
  <iframe
    ref="frame"
    class="python-analysis-frame"
    src="/python-analysis/"
    title="Python 分析工作台"
    @load="syncToken"
  />
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from "vue";

const frame = ref(null);
let syncedToken = "";
let resizeObserver;
let mutationObserver;

const syncToken = async () => {
  const token = localStorage.getItem("token");
  const childWindow = frame.value?.contentWindow;
  if (!childWindow) return;
  if (token !== syncedToken) {
    try {
      const response = await fetch("/python-analysis/session", {
        method: token ? "POST" : "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "same-origin",
      });
      if (!response.ok) return;
      syncedToken = token || "";
      if (token) {
        childWindow.location.reload();
        return;
      }
    } catch {
      return;
    }
  }

  const childDocument = childWindow.document;
  const updateHeight = () => {
    frame.value.style.height = `${Math.max(childDocument.documentElement.scrollHeight, 1800)}px`;
  };
  resizeObserver?.disconnect();
  mutationObserver?.disconnect();
  resizeObserver = new ResizeObserver(updateHeight);
  resizeObserver.observe(childDocument.documentElement);
  mutationObserver = new MutationObserver(updateHeight);
  mutationObserver.observe(childDocument.body, { childList: true, subtree: true, attributes: true });
  updateHeight();
};

onMounted(() => {
  window.addEventListener("auth-changed", syncToken);
  window.addEventListener("storage", syncToken);
});

onBeforeUnmount(() => {
  window.removeEventListener("auth-changed", syncToken);
  window.removeEventListener("storage", syncToken);
  resizeObserver?.disconnect();
  mutationObserver?.disconnect();
});
</script>

<style scoped>
.python-analysis-frame {
  display: block;
  width: 100%;
  height: max(1800px, 100vh);
  border: 0;
  background: transparent;
}
</style>
