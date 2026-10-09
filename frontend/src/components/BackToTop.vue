<template>
  <transition name="fade">
    <button
      v-show="visible"
      class="back-to-top"
      @click="scrollToTop"
      title="回到顶部"
    >
      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
        <path d="M12 4l-8 8h5v8h6v-8h5z" />
      </svg>
    </button>
  </transition>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";

const visible = ref(false);
const threshold = 200;

const handleScroll = () => {
  visible.value = window.scrollY > threshold;
};

const scrollToTop = () => {
  window.scrollTo({
    top: 0,
    behavior: "smooth",
  });
};

onMounted(() => {
  window.addEventListener("scroll", handleScroll);
});

onUnmounted(() => {
  window.removeEventListener("scroll", handleScroll);
});
</script>

<style scoped>
.back-to-top {
  position: fixed;
  right: 24px;
  bottom: 24px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #39a0ff 0%, #5b8def 100%);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(57, 160, 255, 0.4);
  transition: all 0.3s ease;
  z-index: 1000;
}

.back-to-top:hover {
  transform: translateY(-4px);
  box-shadow: 0 6px 20px rgba(57, 160, 255, 0.5);
}

.back-to-top:active {
  transform: translateY(-2px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
