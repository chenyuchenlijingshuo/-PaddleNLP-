<template>
  <iframe
    ref="frame"
    class="python-process-frame"
    src="/python-process/"
    title="Python 数据处理"
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
      const response = await fetch("/python-process/session", {
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
    frame.value.style.height = `${Math.max(childDocument.documentElement.scrollHeight, 1200)}px`;
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
.python-process-frame {
  display: block;
  width: 100%;
  height: max(1200px, 100vh);
  border: 0;
  background: transparent;
}
</style>
