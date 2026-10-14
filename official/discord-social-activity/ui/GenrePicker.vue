<script setup>
import { ref } from "vue";
const props = defineProps({ modelValue: { type: Array, default: () => [] }, options: Array, label: String });
const emit = defineEmits(["update:modelValue"]);
const chosen = ref("");
function add() {
  if (chosen.value && !props.modelValue.includes(chosen.value) && props.modelValue.length < 10)
    emit("update:modelValue", [...props.modelValue, chosen.value]);
  chosen.value = "";
}
</script>
<template>
  <div class="genre-picker"><label>{{ label }}<select v-model="chosen" @change="add" :disabled="modelValue.length >= 10"><option value="">Choose a genre…</option><option v-for="genre in options" :key="genre" :disabled="modelValue.includes(genre)">{{ genre }}</option></select></label><div class="genre-chips"><button v-for="genre in modelValue" :key="genre" type="button" class="pill" :aria-label="'Remove ' + genre + ' from ' + label" @click="emit('update:modelValue', modelValue.filter(value => value !== genre))">{{ genre }} ×</button></div></div>
</template>
<style>
.genre-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:-8px;margin-bottom:12px}.genre-chips .pill{padding:5px 9px}
</style>
