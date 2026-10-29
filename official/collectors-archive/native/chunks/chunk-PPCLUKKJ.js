import {
  defineComponent,
  h,
  host,
  inject
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/native/router.ts
function archivePath(path) {
  const [pathname, query] = path.split("?");
  const match = pathname.match(/^\/(cards|sets)(?:\/([^/]+))?$/);
  if (match) {
    const page = match[2] ? match[1] === "cards" ? "card-detail" : "set-detail" : match[1];
    const params = new URLSearchParams(query);
    if (match[2]) params.set("record_id", match[2]);
    const suffix = params.toString();
    return `/plugins/official.collectors-archive/${page}${suffix ? "?" + suffix : ""}`;
  }
  if (pathname === "/bounties") return "/plugins/official.collectors-archive/bounties" + (query ? "?" + query : "");
  return path;
}
function useRouter() {
  return { push: (path) => host().navigate(archivePath(path)) };
}
function useRoute() {
  return inject("collector-route", { params: { cardId: "", setId: "", id: "" }, query: {} });
}
var RouterLink = defineComponent({
  props: { to: { type: String, required: true } },
  setup(props, { slots, attrs }) {
    return () => h("a", { ...attrs, href: archivePath(props.to), onClick(event) {
      if (event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      void host().navigate(archivePath(props.to));
    } }, slots.default?.());
  }
});

export {
  useRouter,
  useRoute,
  RouterLink
};
