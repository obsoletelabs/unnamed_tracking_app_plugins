// public-runtime:bindings
var BaseTransition;
var BaseTransitionPropsValidators;
var Comment;
var DeprecationTypes;
var EffectScope;
var ErrorCodes;
var ErrorTypeStrings;
var Fragment;
var KeepAlive;
var ReactiveEffect;
var Static;
var Suspense;
var Teleport;
var Text;
var TrackOpTypes;
var Transition;
var TransitionGroup;
var TriggerOpTypes;
var VueElement;
var __esModule;
var assertNumber;
var callWithAsyncErrorHandling;
var callWithErrorHandling;
var camelize;
var capitalize;
var cloneVNode;
var compatUtils;
var compile;
var computed;
var createApp;
var createBlock;
var createCommentVNode;
var createElementBlock;
var createElementVNode;
var createHydrationRenderer;
var createPropsRestProxy;
var createRenderer;
var createSSRApp;
var createSlots;
var createStaticVNode;
var createTextVNode;
var createVNode;
var customRef;
var defineAsyncComponent;
var defineComponent;
var defineCustomElement;
var defineEmits;
var defineExpose;
var defineModel;
var defineOptions;
var defineProps;
var defineSSRCustomElement;
var defineSlots;
var devtools;
var effect;
var effectScope;
var getCurrentInstance;
var getCurrentScope;
var getCurrentWatcher;
var getTransitionRawChildren;
var guardReactiveProps;
var h;
var handleError;
var hasInjectionContext;
var hydrate;
var hydrateOnIdle;
var hydrateOnInteraction;
var hydrateOnMediaQuery;
var hydrateOnVisible;
var initCustomFormatter;
var initDirectivesForSSR;
var inject;
var isMemoSame;
var isProxy;
var isReactive;
var isReadonly;
var isRef;
var isRuntimeOnly;
var isShallow;
var isVNode;
var markRaw;
var mergeDefaults;
var mergeModels;
var mergeProps;
var nextTick;
var nodeOps;
var normalizeClass;
var normalizeProps;
var normalizeStyle;
var onActivated;
var onBeforeMount;
var onBeforeUnmount;
var onBeforeUpdate;
var onDeactivated;
var onErrorCaptured;
var onMounted;
var onRenderTracked;
var onRenderTriggered;
var onScopeDispose;
var onServerPrefetch;
var onUnmounted;
var onUpdated;
var onWatcherCleanup;
var openBlock;
var patchProp;
var popScopeId;
var provide;
var proxyRefs;
var pushScopeId;
var queuePostFlushCb;
var reactive;
var readonly;
var ref;
var registerRuntimeCompiler;
var render;
var renderList;
var renderSlot;
var resolveComponent;
var resolveDirective;
var resolveDynamicComponent;
var resolveFilter;
var resolveTransitionHooks;
var setBlockTracking;
var setDevtoolsHook;
var setTransitionHooks;
var shallowReactive;
var shallowReadonly;
var shallowRef;
var ssrContextKey;
var ssrUtils;
var stop;
var toDisplayString;
var toHandlerKey;
var toHandlers;
var toRaw;
var toRef;
var toRefs;
var toValue;
var transformVNodeArgs;
var triggerRef;
var unref;
var useAttrs;
var useCssModule;
var useCssVars;
var useHost;
var useId;
var useModel;
var useSSRContext;
var useShadowRoot;
var useSlots;
var useTemplateRef;
var useTransitionState;
var vModelCheckbox;
var vModelDynamic;
var vModelRadio;
var vModelSelect;
var vModelText;
var vShow;
var version;
var warn;
var watch;
var watchEffect;
var watchPostEffect;
var watchSyncEffect;
var withAsyncContext;
var withCtx;
var withDefaults;
var withDirectives;
var withKeys;
var withMemo;
var withModifiers;
var withScopeId;
var PageHeader;
var UiModal;
var AppIcon;
var AccountChip;
var PasswordInput;
function configure(context2) {
  ({ BaseTransition, BaseTransitionPropsValidators, Comment, DeprecationTypes, EffectScope, ErrorCodes, ErrorTypeStrings, Fragment, KeepAlive, ReactiveEffect, Static, Suspense, Teleport, Text, TrackOpTypes, Transition, TransitionGroup, TriggerOpTypes, VueElement, __esModule, assertNumber, callWithAsyncErrorHandling, callWithErrorHandling, camelize, capitalize, cloneVNode, compatUtils, compile, computed, createApp, createBlock, createCommentVNode, createElementBlock, createElementVNode, createHydrationRenderer, createPropsRestProxy, createRenderer, createSSRApp, createSlots, createStaticVNode, createTextVNode, createVNode, customRef, defineAsyncComponent, defineComponent, defineCustomElement, defineEmits, defineExpose, defineModel, defineOptions, defineProps, defineSSRCustomElement, defineSlots, devtools, effect, effectScope, getCurrentInstance, getCurrentScope, getCurrentWatcher, getTransitionRawChildren, guardReactiveProps, h, handleError, hasInjectionContext, hydrate, hydrateOnIdle, hydrateOnInteraction, hydrateOnMediaQuery, hydrateOnVisible, initCustomFormatter, initDirectivesForSSR, inject, isMemoSame, isProxy, isReactive, isReadonly, isRef, isRuntimeOnly, isShallow, isVNode, markRaw, mergeDefaults, mergeModels, mergeProps, nextTick, nodeOps, normalizeClass, normalizeProps, normalizeStyle, onActivated, onBeforeMount, onBeforeUnmount, onBeforeUpdate, onDeactivated, onErrorCaptured, onMounted, onRenderTracked, onRenderTriggered, onScopeDispose, onServerPrefetch, onUnmounted, onUpdated, onWatcherCleanup, openBlock, patchProp, popScopeId, provide, proxyRefs, pushScopeId, queuePostFlushCb, reactive, readonly, ref, registerRuntimeCompiler, render, renderList, renderSlot, resolveComponent, resolveDirective, resolveDynamicComponent, resolveFilter, resolveTransitionHooks, setBlockTracking, setDevtoolsHook, setTransitionHooks, shallowReactive, shallowReadonly, shallowRef, ssrContextKey, ssrUtils, stop, toDisplayString, toHandlerKey, toHandlers, toRaw, toRef, toRefs, toValue, transformVNodeArgs, triggerRef, unref, useAttrs, useCssModule, useCssVars, useHost, useId, useModel, useSSRContext, useShadowRoot, useSlots, useTemplateRef, useTransitionState, vModelCheckbox, vModelDynamic, vModelRadio, vModelSelect, vModelText, vShow, version, warn, watch, watchEffect, watchPostEffect, watchSyncEffect, withAsyncContext, withCtx, withDefaults, withDirectives, withKeys, withMemo, withModifiers, withScopeId } = context2.vue);
  ({ PageHeader, UiModal, AppIcon, AccountChip, PasswordInput } = context2.ui);
}

// official/collectors-archive/ui/native/host.ts
var context;
function configureHost(value) {
  context = value;
}
function host() {
  return context.host;
}
async function archiveAction(values, action = "api") {
  const encoded = JSON.stringify(values).replace(
    /[\u0080-\uffff]/g,
    (character) => "\\u" + character.charCodeAt(0).toString(16).padStart(4, "0")
  );
  let request = values;
  let token;
  try {
    if (new TextEncoder().encode(encoded).length > 32e3) {
      token = crypto.randomUUID();
      const count = Math.ceil(encoded.length / 8e3);
      for (let start = 0; start < count; start += 4) {
        await Promise.all(Array.from({ length: Math.min(4, count - start) }, (_, offset) => {
          const index = start + offset;
          return host().runAction("transport-write", { token, count, index, content: encoded.slice(index * 8e3, (index + 1) * 8e3) });
        }));
      }
      request = { request_id: token };
    }
    const result = await host().runAction(action, request);
    const transfer = result.transfer;
    if (!transfer) return result;
    try {
      const chunks = [];
      for (let start = 0; start < transfer.count; start += 4) {
        const batch = await Promise.all(Array.from(
          { length: Math.min(4, transfer.count - start) },
          (_, offset) => host().runAction("transport-read", { token: transfer.token, index: start + offset })
        ));
        chunks.push(...batch.map((chunk) => String(chunk.content)));
      }
      return JSON.parse(chunks.join(""));
    } finally {
      await host().runAction("transport-drop", { token: transfer.token });
    }
  } finally {
    if (token) await host().runAction("transport-drop", { token });
  }
}
async function pluginRequest(path, options = {}) {
  let result = await archiveAction({
    path,
    method: options.method ?? "GET",
    body: options.body ? JSON.parse(String(options.body)) : {}
  });
  const body = result.body;
  while (result.next_offset != null) {
    const [pathname, query] = path.split("?");
    const params = new URLSearchParams(query);
    params.set("offset", String(result.next_offset));
    result = await archiveAction({ path: pathname + "?" + params, method: "GET" });
    if (Number(result.status_code) >= 400) return new Response(JSON.stringify(result.body), { status: Number(result.status_code) });
    if (Array.isArray(body)) body.push(...result.body);
    else for (const key of ["bounties", "transactions"]) {
      const aggregate = body;
      const page = result.body;
      if (Array.isArray(aggregate[key])) aggregate[key].push(...page[key]);
    }
  }
  const status = Number(result.status_code ?? 200);
  return new Response(status === 204 ? null : JSON.stringify(body), { status });
}

export {
  Fragment,
  computed,
  createBlock,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createTextVNode,
  createVNode,
  defineAsyncComponent,
  defineComponent,
  h,
  inject,
  normalizeClass,
  normalizeStyle,
  onBeforeUnmount,
  onMounted,
  openBlock,
  provide,
  ref,
  renderList,
  toDisplayString,
  unref,
  vModelSelect,
  vModelText,
  vShow,
  watch,
  withCtx,
  withDirectives,
  withModifiers,
  PageHeader,
  UiModal,
  AccountChip,
  configure,
  configureHost,
  host,
  archiveAction,
  pluginRequest
};
