/** Official Settings UI. No host imports, credentials, or private endpoints. */
export const locationText = (session) =>
  [session.location?.city, session.location?.region, session.location?.country]
    .filter(Boolean)
    .join(", ") ||
  session.location?.network_label ||
  "Location unavailable";
export const when = (value) =>
  value == null ? "Unavailable" : new Date(value * 1000).toLocaleString();

// Keep this presentation local to the plugin's public UI boundary.
export function sessionDevice(agent) {
  if (!agent) return "Browser unavailable";
  const browser = /Edg(?:e|A|iOS)?\//.test(agent)
    ? "Edge"
    : /(?:Firefox|FxiOS)\//.test(agent)
      ? "Firefox"
      : /(?:Chrome|CriOS)\//.test(agent)
        ? "Chrome"
        : /Safari\//.test(agent)
          ? "Safari"
          : "Other browser";
  const system = /Android/.test(agent)
    ? "Android"
    : /iPhone|iPad|iPod/.test(agent)
      ? "iOS"
      : /Windows/.test(agent)
        ? "Windows"
        : /Macintosh|Mac OS X/.test(agent)
          ? "macOS"
          : /Linux/.test(agent)
            ? "Linux"
            : "";
  return system ? `${browser} on ${system}` : browser;
}

export function createController(
  host,
  admin = false,
  makeReactive = (value) => value,
) {
  const state = makeReactive({
    sessions: [],
    filters: { q: "", state: "", country: "", anomaly: false, user_id: "" },
    cursor: null,
    busy: false,
    error: "",
    notice: "",
    geo: null,
    isAdmin: false,
    compact: false,
  });
  let generation = 0;
  let appliedFilters = { ...state.filters };
  return {
    state,
    async load(append = false) {
      if (state.busy) return;
      state.busy = true;
      state.error = "";
      const current = ++generation;
      try {
        const filters = { ...(append ? appliedFilters : state.filters) };
        if (!filters.anomaly) delete filters.anomaly;
        if (!admin) delete filters.user_id;
        const result = await host.runAction(
          admin ? "list-admin-sessions" : "list-sessions",
          {
            ...filters,
            limit: 200,
            ...(append ? { cursor: state.cursor } : {}),
          },
        );
        if (current !== generation) return;
        appliedFilters = { ...filters };
        state.sessions = append
          ? [...state.sessions, ...result.sessions]
          : result.sessions;
        state.cursor = result.next_cursor;
        state.isAdmin = result.is_admin;
        state.geo = result.geoip;
      } catch (error) {
        state.error = error.message || "Could not load sessions.";
      } finally {
        if (current === generation) state.busy = false;
      }
    },
    async revoke(action, values = {}, signsOut = false) {
      if (state.busy) return;
      state.busy = true;
      state.error = "";
      state.notice = "";
      let completed = false,
        signedOut = false;
      try {
        const result = await host.runAction(action, values);
        if (result.cancelled) return;
        completed = true;
        state.notice =
          typeof result.revoked === "number"
            ? `${result.revoked} sessions revoked.`
            : "Session revoked.";
        signedOut = signsOut || result.current_revoked;
        if (signedOut) await host.navigate("/login");
      } catch (error) {
        state.error = error.message || "Could not revoke sessions.";
      } finally {
        state.busy = false;
      }
      if (completed && !signedOut) await this.load();
    },
    dispose() {
      ++generation;
    },
  };
}

export function project(lat, lon, zoom) {
  const scale = 256 * 2 ** zoom;
  const radians =
    (Math.max(-85.05112878, Math.min(85.05112878, lat)) * Math.PI) / 180;
  return {
    x: ((lon + 180) / 360) * scale,
    y: ((1 - Math.asinh(Math.tan(radians)) / Math.PI) / 2) * scale,
  };
}
export function clusterPoints(sessions, zoom) {
  const clusters = [];
  for (const session of sessions) {
    const { latitude, longitude } = session.location || {};
    if (
      session.state === "revoked" ||
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude)
    )
      continue;
    const point = project(latitude, longitude, zoom);
    const threshold = Math.max(18, 48 - zoom * 3);
    const cluster = clusters.find(
      (item) =>
        Math.abs(item.x - point.x) < threshold &&
        Math.abs(item.y - point.y) < threshold,
    );
    if (cluster) {
      const n = cluster.sessions.length;
      cluster.x = (cluster.x * n + point.x) / (n + 1);
      cluster.y = (cluster.y * n + point.y) / (n + 1);
      cluster.sessions.push(session);
    } else clusters.push({ ...point, sessions: [session] });
  }
  return clusters;
}

export function activate(context) {
  const { h, defineComponent, reactive, ref } = context.vue;
  const fullUserAgent = (session) =>
    session.user_agent
      ? h("details", { class: "ssm-user-agent" }, [
          h("summary", "Full user agent"),
          h("p", session.user_agent),
        ])
      : null;
  const deviceDetails = (session) =>
    h("div", [sessionDevice(session.user_agent), fullUserAgent(session)]);
  const active = new Set();
  context.onCleanup(() => {
    for (const dispose of active) dispose();
    active.clear();
  });
  const button = (label, onclick, disabled = false, danger = false) =>
    h(
      "button",
      {
        type: "button",
        onClick: onclick,
        disabled,
        class: danger ? "ssm-danger" : "",
      },
      label,
    );
  const select = (value, options, change, label) =>
    h("label", { class: "ssm-select" }, [
      label,
      h(
        "select",
        {
          value,
          class: "ui-field",
          "aria-label": label,
          onChange: (event) => change(event.target.value),
        },
        options.map(([id, title]) => h("option", { value: id }, title)),
      ),
    ]);

  const MapView = defineComponent({
    props: ["sessions", "admin"],
    setup(props) {
      const viewport = ref(null);
      const map = reactive({
        zoom: 2,
        x: 512,
        y: 450,
        width: 800,
        height: 340,
        selected: [],
      });
      let observer, drag;
      const resize = (element) => {
        if (element === viewport.value) return;
        observer?.disconnect();
        viewport.value = element;
        if (element) {
          observer = new ResizeObserver(() => {
            map.width = element.clientWidth;
            map.height = element.clientHeight;
          });
          observer.observe(element);
        }
      };
      const zoom = (delta) => {
        const next = Math.max(1, Math.min(8, map.zoom + delta));
        const factor = 2 ** (next - map.zoom);
        map.x *= factor;
        map.y *= factor;
        map.zoom = next;
      };
      return () => {
        const scale = 2 ** map.zoom,
          world = 256 * scale;
        const left = map.x - map.width / 2,
          top = map.y - map.height / 2;
        const tiles = [];
        for (
          let y = Math.max(0, Math.floor(top / 256));
          y <= Math.min(scale - 1, Math.floor((top + map.height) / 256));
          y++
        ) {
          for (
            let x = Math.floor(left / 256);
            x <= Math.floor((left + map.width) / 256);
            x++
          ) {
            tiles.push(
              h("img", {
                key: `${map.zoom}/${x}/${y}`,
                class: "ssm-tile",
                alt: "",
                draggable: false,
                referrerpolicy: "origin",
                src: `https://tile.openstreetmap.org/${map.zoom}/${((x % scale) + scale) % scale}/${y}.png`,
                style: {
                  left: `${x * 256 - left}px`,
                  top: `${y * 256 - top}px`,
                },
              }),
            );
          }
        }
        const clusters = clusterPoints(props.sessions, map.zoom);
        const pins = clusters.map((cluster) => {
          const relativeX =
            ((((cluster.x - map.x + world / 2) % world) + world) % world) -
            world / 2;
          let hash = 0;
          for (const char of cluster.sessions[0].user_id || "")
            hash = (hash * 31 + char.charCodeAt(0)) | 0;
          return h(
            "button",
            {
              type: "button",
              class: "ssm-pin",
              key: cluster.sessions.map((s) => s.id).join(","),
              title: cluster.sessions
                .map((s) => `${s.username || "Session"}: ${locationText(s)}`)
                .join("; "),
              "aria-label": `Inspect ${cluster.sessions.length} sessions at ${locationText(cluster.sessions[0])}`,
              style: {
                left: `${relativeX + map.width / 2}px`,
                top: `${cluster.y - top}px`,
                background:
                  props.admin && cluster.sessions.length === 1
                    ? `hsl(${Math.abs(hash) % 360} 70% 40%)`
                    : "",
              },
              onPointerdown: (event) => event.stopPropagation(),
              onClick: () => {
                map.selected = cluster.sessions;
              },
            },
            cluster.sessions.length > 1 ? String(cluster.sessions.length) : "•",
          );
        });
        return h(
          "section",
          { class: "ssm-map-card", "aria-label": "Session GIS map" },
          [
            h("header", [
              h("h3", "Session locations"),
              button("Zoom in", () => zoom(1)),
              button("Zoom out", () => zoom(-1)),
              button("Reset map", () =>
                Object.assign(map, { zoom: 2, x: 512, y: 450 }),
              ),
              `${clusters.reduce((n, c) => n + c.sessions.length, 0)} mapped`,
            ]),
            h(
              "p",
              "Approximate GeoIP locations. Private/local addresses are not plotted. Pan, zoom, or select a pin for details.",
            ),
            h(
              "div",
              {
                class: "ssm-map",
                ref: resize,
                onWheel: (event) => {
                  event.preventDefault();
                  zoom(event.deltaY < 0 ? 1 : -1);
                },
                onPointerdown: (event) => {
                  event.currentTarget.setPointerCapture(event.pointerId);
                  drag = {
                    x: event.clientX,
                    y: event.clientY,
                    cx: map.x,
                    cy: map.y,
                  };
                },
                onPointermove: (event) => {
                  if (drag) {
                    map.x =
                      (((drag.cx - event.clientX + drag.x) % world) + world) %
                      world;
                    map.y = Math.max(
                      0,
                      Math.min(world, drag.cy - event.clientY + drag.y),
                    );
                  }
                },
                onPointerup: () => {
                  drag = null;
                },
                onPointercancel: () => {
                  drag = null;
                },
              },
              [
                ...tiles,
                ...pins,
                h(
                  "a",
                  {
                    class: "ssm-attribution",
                    href: "https://www.openstreetmap.org/copyright",
                    target: "_blank",
                    rel: "noreferrer",
                  },
                  "© OpenStreetMap contributors",
                ),
              ],
            ),
            props.admin
              ? h("p", "Colours identify users. Nearby sessions are clustered.")
              : null,
            map.selected.length
              ? h("aside", [
                  button("Close details", () => {
                    map.selected = [];
                  }),
                  ...map.selected.map((s) =>
                    h(
                      "p",
                      `${s.username || (s.is_current ? "Current session" : "Session")} · ${locationText(s)} · ${s.ip_address || "IP unavailable"} · ${s.location?.network_number ?? ""} ${s.location?.network_organization || ""} · ${sessionDevice(s.user_agent)}`,
                    ),
                  ),
                ])
              : null,
          ],
        );
      };
    },
  });

  const Sessions = defineComponent({
    props: ["pageId", "host"],
    setup(props) {
      const admin = props.pageId === "admin-sessions";
      const host = {
        runAction: props.host.runAction,
        navigate: context.host.navigate,
      };
      const controller = createController(host, admin, reactive);
      const state = controller.state;
      const dispose = () => controller.dispose();
      active.add(dispose);
      const geo = ref(null),
        geoError = ref("");
      void controller.load();
      async function loadGeo() {
        geoError.value = "";
        try {
          geo.value = await host.runAction("geoip-status");
        } catch (error) {
          geoError.value = error.message;
        }
      }
      async function upload(kind, event) {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file || state.busy) return;
        if (file.size > 256 * 1024 * 1024 || !file.size) {
          geoError.value = "Choose a non-empty MMDB file of at most 256 MiB.";
          return;
        }
        if (
          !window.confirm(
            `Replace the host ${kind} GeoIP database with ${file.name}? This affects future session locations for all users.`,
          )
        )
          return;
        state.busy = true;
        geoError.value = "";
        try {
          const body = new FormData();
          body.append("file", file);
          const response = await fetch(
            `/api/plugins/${encodeURIComponent(context.pluginId)}/capabilities/sessions/geoip?kind=${kind}&confirmed=true`,
            { method: "POST", credentials: "include", body },
          );
          if (response.status === 413)
            throw new Error(
              "The upload exceeds the reverse proxy limit. Configure a limit of at least 256 MiB.",
            );
          if (!response.ok) {
            const data = await response.json();
            throw new Error(
              typeof data.detail === "string"
                ? data.detail
                : "Could not replace GeoIP database.",
            );
          }
          await loadGeo();
          state.notice = `${kind} GeoIP database replaced. Existing session locations are unchanged.`;
        } catch (error) {
          geoError.value = error.message;
        } finally {
          state.busy = false;
        }
        await controller.load();
      }
      const revoke = (session) =>
        controller.revoke(
          admin ? "revoke-admin-session" : "revoke-session",
          { session_id: session.id },
          session.is_current,
        );
      const details = (s) => [
        ["State", s.is_current ? "Current session" : s.state],
        ["Location", locationText(s)],
        ["IP address", s.ip_address || "Unavailable"],
        ["Browser", sessionDevice(s.user_agent)],
        ["Network type", s.location?.network_type || "Unavailable"],
        ["Network", s.location?.network_label || "Unavailable"],
        ["ASN / network number", s.location?.network_number ?? "Unavailable"],
        [
          "Network organization",
          s.location?.network_organization || "Unavailable",
        ],
        ["Created", when(s.created_at)],
        ["Last activity", when(s.last_seen_at)],
        ["Expires", when(s.expires_at)],
        ...(s.revoked_at ? [["Revoked", when(s.revoked_at)]] : []),
      ];
      return () => {
        const users = new Map(
          state.sessions.map((s) => [s.user_id, s.username]),
        );
        const currentSelected = state.sessions.some(
          (s) => s.is_current && s.user_id === state.filters.user_id,
        );
        return h(
          "section",
          {
            class: `ssm ${state.compact ? "ssm-compact" : ""}`,
            onVnodeUnmounted: () => {
              dispose();
              active.delete(dispose);
            },
          },
          [
            h("header", [
              h("div", [
                h("h2", admin ? "Session Manager" : "Sessions"),
                h(
                  "p",
                  "Browser sessions only. API keys are separate. Location is approximate; VPNs and shared networks can affect it.",
                ),
              ]),
              button("Refresh", () => controller.load(), state.busy),
              button(
                admin ? "Revoke all server sessions" : "Revoke all my sessions",
                () =>
                  controller.revoke(
                    admin ? "revoke-all-admin-sessions" : "revoke-all-sessions",
                    {},
                    true,
                  ),
                state.busy,
                true,
              ),
            ]),
            h(
              "form",
              {
                class: "ssm-toolbar",
                onSubmit: (event) => {
                  event.preventDefault();
                  void controller.load();
                },
              },
              [
                h("label", [
                  "Search",
                  h("input", {
                    value: state.filters.q,
                    maxlength: 200,
                    placeholder: "User, IP, device or location",
                    onInput: (e) => {
                      state.filters.q = e.target.value;
                    },
                  }),
                ]),
                select(
                  state.filters.state,
                  [
                    ["", "All states"],
                    ["active", "Active"],
                    ["expired", "Expired"],
                    ["revoked", "Revoked"],
                  ],
                  (v) => {
                    state.filters.state = v;
                  },
                  "State",
                ),
                h("label", [
                  "Country",
                  h("input", {
                    value: state.filters.country,
                    maxlength: 128,
                    onInput: (e) => {
                      state.filters.country = e.target.value;
                    },
                  }),
                ]),
                h("label", [
                  h("input", {
                    type: "checkbox",
                    checked: state.filters.anomaly,
                    onChange: (e) => {
                      state.filters.anomaly = e.target.checked;
                    },
                  }),
                  "Anomalies only",
                ]),
                h(
                  "button",
                  { type: "submit", disabled: state.busy },
                  "Apply filters",
                ),
                button(
                  "Clear filters",
                  () => {
                    Object.assign(state.filters, {
                      q: "",
                      country: "",
                      state: "",
                      anomaly: false,
                      user_id: "",
                    });
                    void controller.load();
                  },
                  state.busy,
                ),
                admin
                  ? button(
                      state.compact ? "Normal table" : "Compact table",
                      () => {
                        state.compact = !state.compact;
                      },
                    )
                  : null,
              ],
            ),
            admin
              ? h("div", { class: "ssm-toolbar" }, [
                  select(
                    state.filters.user_id,
                    [["", "All users"], ...users.entries()].filter(
                      ([, name]) => name,
                    ),
                    (v) => {
                      state.filters.user_id = v;
                    },
                    "User",
                  ),
                  button(
                    "Revoke all for selected user",
                    () =>
                      controller.revoke(
                        "revoke-user-sessions",
                        { user_id: state.filters.user_id },
                        currentSelected,
                      ),
                    !state.filters.user_id || state.busy,
                    true,
                  ),
                ])
              : null,
            admin
              ? h(
                  "details",
                  {
                    onToggle: (e) => {
                      if (e.target.open && !geo.value) void loadGeo();
                    },
                  },
                  [
                    h("summary", "Configure GeoIP databases"),
                    h(
                      "p",
                      "Optional local MaxMind-compatible MMDB databases. City adds coordinates, Country adds fallback country data, Network adds ASN/network ownership. Replacements affect future logins.",
                    ),
                    geoError.value
                      ? h(
                          "p",
                          { role: "alert", class: "ssm-error" },
                          geoError.value,
                        )
                      : null,
                    ...["city", "country", "network"].map((kind) =>
                      h("label", { class: "ssm-file" }, [
                        `${kind}: ${geo.value?.[kind]?.configured ? "Configured" : "Not configured"}`,
                        h("input", {
                          type: "file",
                          accept: ".mmdb",
                          disabled: state.busy,
                          onChange: (e) => upload(kind, e),
                        }),
                      ]),
                    ),
                    button("Refresh database status", loadGeo, state.busy),
                  ],
                )
              : null,
            state.busy ? h("p", { role: "status" }, "Working…") : null,
            state.error
              ? h("p", { role: "alert", class: "ssm-error" }, state.error)
              : null,
            state.notice ? h("p", { role: "status" }, state.notice) : null,
            state.geo?.city
              ? h(MapView, { sessions: state.sessions, admin })
              : null,
            !state.busy && !state.error && !state.sessions.length
              ? h("p", "No sessions match these filters.")
              : null,
            admin
              ? h("div", { class: "ssm-table-wrap" }, [
                  h("table", [
                    h("thead", [
                      h(
                        "tr",
                        [
                          "User",
                          "State",
                          "Location",
                          "IP",
                          "Device",
                          "Network",
                          "Created",
                          "Last activity",
                          "Expires",
                          "Anomaly",
                          "Actions",
                        ].map((name) => h("th", name)),
                      ),
                    ]),
                    h(
                      "tbody",
                      state.sessions.map((s) =>
                        h(
                          "tr",
                          { key: s.id },
                          [
                            s.username,
                            s.is_current ? "Current session" : s.state,
                            locationText(s),
                            s.ip_address || "Unavailable",
                            deviceDetails(s),
                            [
                              s.location?.network_type,
                              s.location?.network_label,
                              s.location?.network_number,
                              s.location?.network_organization,
                            ]
                              .filter((v) => v != null)
                              .join(" · ") || "Unavailable",
                            when(s.created_at),
                            when(s.last_seen_at),
                            when(s.expires_at),
                            [s.anomaly?.reason, s.anomaly?.previous_location]
                              .filter(Boolean)
                              .join(" · ") || "—",
                          ]
                            .map((value) =>
                              h(
                                "td",
                                {
                                  title:
                                    typeof value === "string"
                                      ? value
                                      : undefined,
                                },
                                value,
                              ),
                            )
                            .concat([
                              h(
                                "td",
                                s.state === "active"
                                  ? button(
                                      "Revoke",
                                      () => revoke(s),
                                      state.busy,
                                      true,
                                    )
                                  : when(s.revoked_at),
                              ),
                            ]),
                        ),
                      ),
                    ),
                  ]),
                ])
              : h(
                  "div",
                  { class: "ssm-list" },
                  state.sessions.map((s) =>
                    h("article", { key: s.id }, [
                      h("header", [
                        h(
                          "h3",
                          s.is_current
                            ? "Current session"
                            : `${s.state} session`,
                        ),
                        s.state === "active" && !s.is_current
                          ? button("Revoke", () => revoke(s), state.busy, true)
                          : null,
                      ]),
                      h(
                        "dl",
                        details(s).flatMap(([label, value]) => [
                          h("dt", label),
                          h("dd", String(value)),
                        ]),
                      ),
                      fullUserAgent(s),
                      s.anomaly?.reason
                        ? h(
                            "p",
                            { class: "ssm-anomaly" },
                            `${s.anomaly.reason} Previous location: ${s.anomaly.previous_location || "Unavailable"}. Location is approximate.`,
                          )
                        : null,
                    ]),
                  ),
                ),
            state.cursor
              ? button(
                  "Load more sessions",
                  () => controller.load(true),
                  state.busy,
                )
              : null,
          ],
        );
      };
    },
  });
  context.registerComponent("sessions", Sessions);
  context.registerComponent("admin-sessions", Sessions);
}
