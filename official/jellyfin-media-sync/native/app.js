export function activate(context) {
  const { h, ref, reactive, defineComponent, onBeforeUnmount } = context.vue;
  const cleanups = new Set();
  context.onCleanup(() => {
    for (const stop of cleanups) stop();
    cleanups.clear();
  });
  function lifetime() {
    const state = { live: true, timer: null };
    const stop = () => {
      state.live = false;
      clearTimeout(state.timer);
      cleanups.delete(stop);
    };
    cleanups.add(stop);
    onBeforeUnmount(stop);
    return state;
  }
  function page(admin) {
    return defineComponent({
      props: ["host"],
      setup(props) {
        const life = lifetime();
        const config = ref({
          servers: [],
          accounts: [],
          reviews: [],
          is_admin: false,
        });
        const statuses = ref({});
        const busy = ref(false);
        const loading = ref(true);
        const configurationError = ref("");
        const message = ref("");
        const warnings = ref([]);
        const pending = ref(null);
        const serverForm = reactive({
          name: "",
          url: "",
          server_id: "",
          interval_minutes: 15,
          max_retries: 4,
          history_days: 30,
          enabled: true,
          api_key: "",
        });
        const loginForm = reactive({
          server_id: "",
          account_id: "",
          username: "",
          password: "",
          remote_user_id: "",
        });
        const approval = reactive({
          server_id: "",
          host_user_id: "",
          remote_user_id: "",
          approved: true,
        });
        const drafts = reactive({});
        const episodeDrafts = reactive({});
        const mappings = reactive({});
        const run = (id, values = {}) => props.host.runAction(id, values);
        async function refresh(preserveDrafts = false) {
          const result = await run("get-config");
          if (!life.live) return;
          config.value = result;
          for (const review of result.reviews || []) {
            const key = `${review.account_id}:${review.external_id}`;
            if (!episodeDrafts[key])
              episodeDrafts[key] = { season: 1, number: 1 };
          }
          for (const account of result.accounts || [])
            if (!preserveDrafts || !drafts[account.id])
              drafts[account.id] = {
                ...account,
                libraries: [...(account.libraries || [])],
              };
          for (const server of result.servers || [])
            if (!preserveDrafts || !mappings[server.id])
              mappings[server.id] = { ...(server.mappings || {}) };
        }
        async function perform(id, values = {}) {
          busy.value = true;
          try {
            const result = await run(id, values);
            if (!life.live || result.cancelled) return;
            message.value =
              result.message ||
              (result.ok ? "Saved." : "Operation needs attention.");
            warnings.value = result.warnings || [];
            if (result.pending_id) pending.value = result;
            if (id === "quick-connect-finish" && result.ok)
              pending.value = null;
            await refresh();
          } catch (error) {
            if (life.live)
              message.value =
                error?.message || "Operation failed. Check credentials, server access and plugin permissions in runtime diagnostics.";
          } finally {
            if (life.live) {
              busy.value = false;
              if (!admin) {
                clearTimeout(life.timer);
                life.timer = setTimeout(poll, 1000);
              }
            }
          }
        }
        let lastReviewSignature = null;
        async function poll() {
          let interval = 30000;
          try {
            if (!life.live) return;
            if ((typeof document !== "undefined" && document.hidden) || busy.value) return;
            const result = await run("status");
            if (!life.live) return;
            statuses.value = result.accounts || {};
            const entries = Object.entries(statuses.value).sort(([a], [b]) => a.localeCompare(b));
            if (entries.some(([, state]) => state.phase === "syncing")) interval = 5000;
            const signature = JSON.stringify(entries.map(([id, state]) => [id, state.reviews || 0, state.finished_at || 0]));
            const reviews = entries.reduce((total, [, state]) => total + (state.reviews || 0), 0);
            if ((lastReviewSignature !== null && lastReviewSignature !== signature) ||
                reviews !== (config.value.review_total ?? config.value.reviews?.length ?? 0))
              await refresh(true);
            lastReviewSignature = signature;
          } catch (error) {
            if (life.live)
              message.value =
                error?.message || "Sync status is unavailable. Check plugin permissions.";
          } finally {
            if (life.live) life.timer = setTimeout(poll, interval);
          }
        }
        async function loadConfiguration() {
          loading.value = true;
          configurationError.value = "";
          try {
            await refresh();
            if (life.live && !admin) poll();
          } catch (error) {
            if (life.live) configurationError.value = error?.message || "Check the plugin's enabled state and storage permission in Plugin Manager.";
          } finally {
            if (life.live) loading.value = false;
          }
        }
        loadConfiguration();
        const button = (label, id, values = () => ({})) =>
          h(
            "button",
            {
              type: "button",
              disabled: busy.value,
              onClick: () => perform(id, values()),
            },
            label,
          );
        const field = (target, key, label, type = "text") =>
          h("label", { class: "jf-field" }, [
            h("span", label),
            type === "password" && context.ui?.PasswordInput ? h(context.ui.PasswordInput, {
              modelValue: target[key], disabled: busy.value, mode: "replace",
              inputAriaLabel: label, autocomplete: "new-password",
              "onUpdate:modelValue": value => { target[key] = value; },
            }) : h("input", {
              type,
              value: target[key],
              disabled: busy.value,
              autocomplete: type === "password" ? "new-password" : "off",
              onInput: (event) => {
                target[key] =
                  type === "number"
                    ? Number(event.target.value)
                    : event.target.value;
              },
            }),
          ]);
        const toggle = (target, key, label) =>
          h("label", { class: "jf-check" }, [
            h("input", {
              type: "checkbox",
              checked: target[key],
              disabled: busy.value,
              onChange: (event) => {
                target[key] = event.target.checked;
              },
            }),
            label,
          ]);
        const select = (target, key, label, choices) =>
          h("label", { class: "jf-field" }, [
            h("span", label),
            h(
              "select",
              {
                value: target[key],
                disabled: busy.value,
                onChange: (event) => {
                  target[key] = event.target.value;
                },
              },
              [
                h("option", { value: "" }, "Choose…"),
                ...choices.map((value) =>
                  h("option", { value: value.id }, value.name),
                ),
              ],
            ),
          ]);
        const panel = (title, children, attrs = {}) =>
          h("section", { class: "jf-panel", ...attrs }, [
            h("h3", title),
            ...children,
          ]);
        const accountPanel = (account) => {
          const draft = drafts[account.id] || account;
          const server = config.value.servers.find(
            (s) => s.id === account.server_id,
          );
          const status = statuses.value[account.id] || { phase: "idle" };
          const libraries = (server?.libraries || []).filter(
            (l) => !server.mappings || server.mappings[l.id] !== "ignore",
          );
          return panel(
            `${account.name} · ${server?.name || "Server unavailable"}`,
            [
              h(
                "p",
                account.credential_configured
                  ? "Credential configured"
                  : "Reconnect needed · saved configuration retained",
              ),
              ...[
                ["enabled", "Account enabled"],
                ["background_sync", "Automatic sync"],
                [
                  "auto_merge",
                  "Merge provider IDs and unique title/year matches",
                ],
                [
                  "notifications",
                  "Notify me about errors (requires permission)",
                ],
                ["history_enabled", "Import sessions from Playback Reporting"],
              ].map(([key, label]) => toggle(draft, key, label)),
              h("fieldset", [
                h(
                  "legend",
                  "Library selection · none selected uses all approved libraries",
                ),
                ...libraries.map((library) =>
                  h("label", { class: "jf-check" }, [
                    h("input", {
                      type: "checkbox",
                      checked: draft.libraries.includes(library.id),
                      onChange: (event) => {
                        draft.libraries = event.target.checked
                          ? [...draft.libraries, library.id]
                          : draft.libraries.filter((id) => id !== library.id);
                      },
                    }),
                    library.name,
                  ]),
                ),
              ]),
              h("div", { class: "jf-actions" }, [
                button("Save preferences", "save-account", () => ({
                  account_id: account.id,
                  ...Object.fromEntries(
                    [
                      "enabled",
                      "background_sync",
                      "auto_merge",
                      "notifications",
                      "history_enabled",
                      "libraries",
                    ].map((key) => [key, draft[key]]),
                  ),
                })),
                button("Sync now", "sync-now", () => ({
                  account_id: account.id,
                })),
                button("Full rescan", "sync-now", () => ({
                  account_id: account.id,
                  rescan: true,
                })),
              ]),
              h("div", { class: "jf-actions" }, [
                h(
                  "button",
                  {
                    type: "button",
                    disabled: busy.value,
                    onClick: () => {
                      loginForm.server_id = account.server_id;
                      loginForm.account_id = account.id;
                      loginForm.username = account.name;
                      message.value =
                        "Use the connection panel to replace this account's credential.";
                    },
                  },
                  "Reconnect",
                ),
                button("Remove credential", "clear-account-credential", () => ({
                  account_id: account.id,
                })),
              ]),
              h(
                "div",
                { class: "jf-actions" },
                [-1, 1].map((direction) =>
                  h(
                    "button",
                    {
                      type: "button",
                      disabled:
                        busy.value ||
                        config.value.accounts.indexOf(account) + direction <
                          0 ||
                        config.value.accounts.indexOf(account) + direction >=
                          config.value.accounts.length,
                      onClick: () => {
                        const order = config.value.accounts.map((a) => a.id);
                        const index = order.indexOf(account.id);
                        [order[index], order[index + direction]] = [
                          order[index + direction],
                          order[index],
                        ];
                        perform("order-accounts", { account_ids: order });
                      },
                    },
                    direction < 0
                      ? "Higher Watch Now priority"
                      : "Lower priority",
                  ),
                ),
              ),
              h("div", { role: "status", class: "jf-status" }, [
                h("strong", status.phase),
                h(
                  "span",
                  ` · ${status.processed || 0} items · ${status.reviews || 0} reviews`,
                ),
                status.stage
                  ? h(
                      "p",
                      `Stage: ${status.stage} · library ${Math.min((status.library_index || 0) + 1, status.library_total || 1)} / ${status.library_total || 1} · ${status.offset || 0}${status.page_total != null ? ` / ${status.page_total}` : ""}`,
                    )
                  : null,
                status.error
                  ? h("p", { class: "jf-error" }, status.error)
                  : null,
                status.history_warning
                  ? h("p", { class: "jf-warning" }, status.history_warning)
                  : null,
                status.retry_at
                  ? h(
                      "p",
                      `Retry limit is configurable by the administrator. Next automatic run replaces the retry schedule.`,
                    )
                  : null,
              ]),
            ],
            { "data-testid": "jf-account" },
          );
        };
        function userContents() {
          const selected = config.value.servers.find(
            (s) => s.id === loginForm.server_id,
          );
          return [
            panel(
              loginForm.account_id
                ? "Reconnect your account"
                : "Connect another account",
              [
                select(
                  loginForm,
                  "server_id",
                  "Jellyfin server",
                  config.value.servers.filter((s) => s.enabled),
                ),
                field(loginForm, "username", "Username"),
                field(loginForm, "password", "Password", "password"),
                h("div", { class: "jf-actions" }, [
                  button("Sign in", "login", () => {
                    const values = { ...loginForm };
                    loginForm.password = "";
                    return values;
                  }),
                  button("Quick Connect", "quick-connect-start", () => ({
                    server_id: loginForm.server_id,
                    account_id: loginForm.account_id || undefined,
                  })),
                  h(
                    "button",
                    {
                      type: "button",
                      onClick: () => {
                        loginForm.account_id = "";
                        loginForm.username = "";
                        loginForm.password = "";
                      },
                    },
                    "New account",
                  ),
                ]),
                pending.value
                  ? h("div", { class: "jf-warning" }, [
                      h(
                        "p",
                        `Approve code ${pending.value.code} in Jellyfin within five minutes.`,
                      ),
                      button("Check approval", "quick-connect-finish", () => ({
                        pending_id: pending.value.pending_id,
                      })),
                    ])
                  : null,
                selected?.approved_users?.length
                  ? h("div", [
                      select(
                        loginForm,
                        "remote_user_id",
                        "Administrator-approved identity",
                        selected.approved_users,
                      ),
                      button("Link approved identity", "link-approved", () => ({
                        server_id: loginForm.server_id,
                        remote_user_id: loginForm.remote_user_id,
                        account_id: loginForm.account_id || undefined,
                      })),
                    ])
                  : null,
                h(
                  "p",
                  "Passwords are used for login only. Tokens stay in the plugin's private broker storage.",
                ),
              ],
            ),
            ...config.value.accounts.map(accountPanel),
            panel(`Review queue · ${config.value.review_total || 0}`, [
              h(
                "p",
                "Ambiguous matches, category changes and local watch-state edits need a decision. The first 50 pending items are shown.",
              ),
              ...config.value.reviews.map((review) =>
                h("article", { class: "jf-review" }, [
                  h("strong", review.title),
                  h("p", review.reason.replaceAll("_", " ")),
                  h("div", { class: "jf-actions" }, [
                    button("Skip item", "resolve-review", () => ({
                      ...review,
                      decision: "skip",
                    })),
                    ...(review.reason === "missing_episode_number"
                      ? [
                          field(
                            episodeDrafts[
                              `${review.account_id}:${review.external_id}`
                            ],
                            "season",
                            "Season (zero for specials)",
                            "number",
                          ),
                          field(
                            episodeDrafts[
                              `${review.account_id}:${review.external_id}`
                            ],
                            "number",
                            "Episode number",
                            "number",
                          ),
                          button(
                            "Assign episode number",
                            "resolve-review",
                            () => ({
                              ...review,
                              decision: "map_episode",
                              ...episodeDrafts[
                                `${review.account_id}:${review.external_id}`
                              ],
                            }),
                          ),
                        ]
                      : []),
                    ...(!review.host_id &&
                    review.reason !== "missing_episode_number"
                      ? [
                          button(
                            "Create separate item",
                            "resolve-review",
                            () => ({ ...review, decision: "new" }),
                          ),
                        ]
                      : []),
                    ...review.candidates.map((candidate) =>
                      button(
                        `Merge with ${candidate.title}`,
                        "resolve-review",
                        () => ({
                          ...review,
                          decision: "merge",
                          target_id: candidate.id,
                        }),
                      ),
                    ),
                    ...(review.reason === "local_watch_state_changed"
                      ? [
                          button(
                            "Use Jellyfin watch state",
                            "resolve-review",
                            () => ({ ...review, decision: "use_remote" }),
                          ),
                        ]
                      : []),
                    ...(review.reason === "category_changed"
                      ? [
                          button(
                            "Keep existing category",
                            "resolve-review",
                            () => ({ ...review, decision: "keep_category" }),
                          ),
                        ]
                      : []),
                  ]),
                ]),
              ),
            ]),
          ];
        }
        function adminContents() {
          if (!config.value.is_admin)
            return [h("p", "Administrator access is required for this page.")];
          return [
            panel(
              "Installation servers",
              [
                ...config.value.servers.map((server) =>
                  h("div", { class: "jf-server" }, [
                    h("strong", server.name),
                    h(
                      "p",
                      `${server.url} · ${server.enabled ? "enabled" : "disabled"} · ${server.credential_configured ? "key configured" : "no discovery key"}`,
                    ),
                    h("div", { class: "jf-actions" }, [
                      h(
                        "button",
                        {
                          type: "button",
                          onClick: () => {
                            Object.assign(serverForm, {
                              ...server,
                              server_id: server.id,
                              api_key: "",
                            });
                          },
                        },
                        "Edit",
                      ),
                      button(
                        "Test connection and discover",
                        "test-connection",
                        () => ({ server_id: server.id }),
                      ),
                      button(
                        "Remove discovery credential",
                        "clear-server-credential",
                        () => ({ server_id: server.id }),
                      ),
                    ]),
                    ...(server.libraries || []).map((library) =>
                      select(mappings[server.id], library.id, library.name, [
                        { id: "ignore", name: "Excluded" },
                        {
                          id: "auto",
                          name: "Approve · automatic film/TV/anime",
                        },
                        { id: "movie", name: "Approve · films" },
                        { id: "tv_show", name: "Approve · TV" },
                        { id: "anime", name: "Approve · anime" },
                      ]),
                    ),
                    button("Save approved libraries", "save-mappings", () => ({
                      server_id: server.id,
                      mappings: { ...mappings[server.id] },
                    })),
                  ]),
                ),
                field(serverForm, "name", "Server name"),
                field(
                  serverForm,
                  "url",
                  "Server URL (base paths supported)",
                  "url",
                ),
                field(
                  serverForm,
                  "api_key",
                  "Discovery API key · blank keeps existing",
                  "password",
                ),
                field(
                  serverForm,
                  "interval_minutes",
                  "Automatic interval (minutes)",
                  "number",
                ),
                field(serverForm, "max_retries", "Maximum retries", "number"),
                field(
                  serverForm,
                  "history_days",
                  "Initial history lookback (days)",
                  "number",
                ),
                toggle(serverForm, "enabled", "Server enabled"),
                h("div", { class: "jf-actions" }, [
                  button("Save server", "save-server", () => {
                    const values = { ...serverForm };
                    serverForm.api_key = "";
                    return values;
                  }),
                  h(
                    "button",
                    {
                      type: "button",
                      onClick: () => {
                        Object.assign(serverForm, {
                          name: "",
                          url: "",
                          server_id: "",
                          api_key: "",
                          interval_minutes: 15,
                          max_retries: 4,
                          history_days: 30,
                          enabled: true,
                        });
                      },
                    },
                    "New server",
                  ),
                ]),
                h(
                  "p",
                  "Music, books, Live TV and collections are excluded. Only approved Movie, Series and Episode items sync. TLS uses the host CA trust store.",
                ),
              ],
              { "data-testid": "jf-admin" },
            ),
            panel("Optional shared-key identity access", [
              h(
                "p",
                "Users can sign in themselves. Approve identities here only when using the installation discovery key for a user's sync.",
              ),
              select(approval, "server_id", "Server", config.value.servers),
              field(approval, "host_user_id", "Host user UUID"),
              select(
                approval,
                "remote_user_id",
                "Jellyfin user",
                config.value.servers.find((s) => s.id === approval.server_id)
                  ?.users || [],
              ),
              toggle(approval, "approved", "Allow this identity"),
              button("Save approval", "authorize-identity", () => ({
                ...approval,
              })),
            ]),
          ];
        }
        function contents() {
          if (loading.value) return [h("p", { role: "status" }, "Loading Jellyfin configuration…")];
          if (configurationError.value) return [panel("Jellyfin configuration unavailable", [
            h("p", { role: "alert", class: "jf-error" }, configurationError.value),
            h("button", { type: "button", onClick: loadConfiguration }, "Retry loading"),
          ])];
          return admin ? adminContents() : userContents();
        }
        return () =>
          h("section", { class: "jf-official jf-sync" }, [
            h(
              "p",
              { class: "jf-badge" },
              `Official preview · ${context.version || "0.0.x"}`,
            ),
            h(
              "h2",
              admin ? "Jellyfin administration" : "Your Jellyfin accounts",
            ),
            h(
              "p",
              admin
                ? "Manage servers and library approval for this installation."
                : "Use every enabled account for sync. Your priority order chooses the Watch Now shortcut.",
            ),
            !admin && !loading.value && !configurationError.value
              ? h("p", [
                  "Your host user ID: ",
                  h("code", config.value.host_user_id || "Loading…"),
                ])
              : null,
            message.value ? h("p", { role: "status" }, message.value) : null,
            ...warnings.value.map((warning) =>
              h("p", { class: "jf-warning", role: "alert" }, warning),
            ),
            ...contents(),
          ]);
      },
    });
  }
  context.registerComponent("accounts", page(false));
  context.registerComponent("admin", page(true));
  context.registerComponent(
    "watch",
    defineComponent({
      props: ["host"],
      setup(props) {
        const life = lifetime();
        const result = ref(null);
        props.host
          .runAction("watch-now")
          .then((value) => {
            if (life.live) result.value = value;
          })
          .catch(() => {
            if (life.live)
              result.value = {
                message: "Jellyfin mapping unavailable. Check account access.",
              };
          });
        return () =>
          h(
            "div",
            { class: "jf-official jf-watch" },
            result.value?.ok
              ? [
                  h(
                    "a",
                    {
                      href: result.value.url,
                      target: "_blank",
                      rel: "noopener noreferrer",
                    },
                    `Watch in Jellyfin · ${result.value.server}`,
                  ),
                ]
              : [
                  h(
                    "span",
                    result.value?.message || "Finding your Jellyfin item…",
                  ),
                ],
          );
      },
    }),
  );
}
