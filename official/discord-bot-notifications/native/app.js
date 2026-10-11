export function activate(context) {
  const { h, reactive, ref, defineComponent, onBeforeUnmount } = context.vue;

  function text(label, value) {
    return h("div", { class: "discord-stat" }, [
      h("span", { class: "discord-stat-label" }, label),
      h("strong", value === null || value === undefined || value === "" ? "—" : String(value)),
    ]);
  }

  function badge(value, positive = false) {
    return h("span", { class: "discord-badge" + (positive ? " discord-badge-good" : "") }, String(value));
  }

  function infoCard(title, children, extraClass = "") {
    return h("section", { class: "discord-panel " + extraClass }, [h("h3", title), ...children]);
  }

  function page(admin) {
    return defineComponent({
      props: ["host"],
      setup(props) {
        const loading = ref(true);
        const busy = ref(false);
        const error = ref("");
        const message = ref("");
        const config = ref({});
        const tokenForm = reactive({ token: "", guild_id: "" });
        const userForm = reactive({ username: "", code: "" });
        const directory = ref(null);
        const channelChoices = ref([]);
        const channelSelection = ref("");
        const allowedChannels = ref([]);
        const memberSelection = ref("");
        const memberSearch = ref("");
        const channelSearch = ref("");
        const accountSearch = ref("");
        const serverSearch = ref("");
        const servers = ref([]);
        const serverCursor = ref(null);
        const destinations = ref([]);
        const destinationError = ref("");
        const destinationCursor = ref(null);
        const matches = (query, ...values) => values.join(" ").toLowerCase().includes(query.trim().toLowerCase());
        const notificationUrl = (destination, provider, adminArea = false) => {
          const query = new URLSearchParams({ area: adminArea ? "administration" : "account", section: "notifications" });
          if (destination) query.set("notification_destination", destination);
          if (provider) query.set("notification_provider", provider);
          return "/settings?" + query;
        };
        let live = true;
        onBeforeUnmount(() => { live = false; });

        async function refresh() {
          loading.value = true;
          error.value = "";
          destinations.value = [];
          destinationCursor.value = null;
          const started = performance.now();
          try {
            const result = await props.host.runAction("get-config");
            if (!live) return;
            config.value = { ...result, browser_refresh_ms: Math.round(performance.now() - started) };
            await loadDestinations();
            if (!admin && result.configured) {
              const choices = await props.host.runAction("channel-choices");
              if (!live) return;
              channelChoices.value = choices.channels || [];
              channelSelection.value = choices.selected || "";
            }
            if (admin && !tokenForm.guild_id) tokenForm.guild_id = result.guild_id || "";
          } catch (err) {
            if (live) error.value = err?.message || "Discord settings could not be loaded.";
          } finally {
            if (live) loading.value = false;
          }
        }

        async function perform(id, values = {}) {
          busy.value = true;
          error.value = "";
          message.value = "";
          try {
            const result = await props.host.runAction(id, values);
            if (!live || result.cancelled) return;
            message.value = result.message || "Done.";
            tokenForm.token = "";
            userForm.code = "";
            await refresh();
          } catch (err) {
            if (live) error.value = err?.message || "Discord operation failed.";
          } finally {
            if (live) busy.value = false;
          }
        }

        async function loadDestinations(after = null) {
          destinationError.value = "";
          // A failed refresh must never leave a previously verified badge on screen.
          if (!after) destinations.value = [];
          try {
            const result = await props.host.runAction("get-destinations", after ? { after } : {});
            if (!live) return;
            const current = after ? destinations.value : [];
            destinations.value = [...new Map([...current, ...(result.destinations || [])].map(item => [item.id, item])).values()];
            destinationCursor.value = result.next_after || null;
          } catch (err) {
            if (live) {
              destinations.value = [];
              destinationCursor.value = null;
              destinationError.value = "Host destination status is unavailable. Review the destination-status permission or open Notifications to check current proof and recovery routing.";
            }
          }
        }

        async function loadServers(after = "0") {
          busy.value = true;
          error.value = "";
          try {
            const result = await props.host.runAction("list-servers", { after, token: tokenForm.token });
            if (!live) return;
            servers.value = [...new Map([...(after === "0" ? [] : servers.value), ...(result.servers || [])].map(item => [item.id, item])).values()];
            serverCursor.value = result.next_after || null;
          } catch (err) {
            if (live) error.value = err?.message || "Discord servers could not be loaded.";
          } finally {
            if (live) busy.value = false;
          }
        }

        const searchField = (label, target, placeholder) => h("label", { class: "discord-field" }, [
          h("span", label), h("input", { type: "search", value: target.value, placeholder,
            onInput: event => { target.value = event.target.value; } }),
        ]);

        async function loadDirectory(after = "0") {
          busy.value = true;
          error.value = "";
          try {
            const result = await props.host.runAction("list-directory", { after });
            if (!live) return;
            directory.value = { ...result, users: after === "0" ? result.users : [...(directory.value?.users || []), ...result.users] };
            allowedChannels.value = result.allowed_channel_ids || [];
          } catch (err) {
            if (live) error.value = err?.message || "Discord directory could not be loaded.";
          } finally {
            if (live) busy.value = false;
          }
        }

        const field = (label, target, key, type = "text", autocomplete = "off") =>
          h("label", { class: "discord-field" }, [
            h("span", label),
            h("input", {
              type,
              value: target[key],
              disabled: busy.value,
              autocomplete,
              onInput: event => { target[key] = event.target.value; },
            }),
          ]);

        const button = (label, id, values = () => ({}), danger = false) =>
          h("button", {
            type: "button",
            disabled: busy.value,
            class: danger ? "discord-danger" : "",
            onClick: () => perform(id, values()),
          }, label);

        const image = (src, alt, className) => src
          ? h("img", { src, alt, class: className, loading: "lazy" })
          : null;

        refresh();

        return () => {
          const c = config.value;
          const bot = c.bot || {};
          const guild = c.guild || {};
          const member = c.bot_member || {};
          const permissions = Array.isArray(member.permission_names) ? member.permission_names : [];
          const roles = Array.isArray(member.role_names) ? member.role_names : [];
          const features = Array.isArray(guild.features) ? guild.features : [];
          const serverStatus = c.health?.api_ok === false ? "Unavailable" : c.configured ? "Connected" : "Not configured";

          const adminCards = [
            infoCard("Connection", [
              h("div", { class: "discord-identity" }, [
                image(bot.avatar_url, bot.username || "Discord bot", "discord-avatar"),
                h("div", [
                  h("strong", bot.global_name || bot.username || "Discord bot"),
                  h("span", "@" + (bot.username || "—")),
                  h("span", { class: "discord-muted" }, "Bot ID: " + (bot.id || "—")),
                ]),
                badge(serverStatus, serverStatus === "Connected"),
              ]),
              c.bot_error ? h("p", { class: "discord-error" }, c.bot_error) : null,
              h("div", { class: "discord-grid" }, [
                text("API health", c.health?.api_ok === false ? "Unavailable" : "Healthy"),
                text("Plugin request", c.health?.request_ms ? c.health.request_ms + " ms" : "—"),
                text("Browser refresh", c.browser_refresh_ms ? c.browser_refresh_ms + " ms" : "—"),
                text("Verified bot", bot.verified === true ? "Yes" : bot.verified === false ? "No" : "Unknown"),
              ]),
              bot.invite_url ? h("a", { href: bot.invite_url, target: "_blank", rel: "noopener noreferrer", class: "discord-link" }, "Open Discord bot invite") : null,
              bot.recommended_intents?.length ? h("p", { class: "discord-hint" }, "Required/recommended intents: " + bot.recommended_intents.join(", ")) : null,
            ]),
            infoCard("Discord server", [
              h("div", { class: "discord-identity" }, [
                image(guild.icon_url, guild.name || "Discord server", "discord-avatar discord-guild-avatar"),
                h("div", [
                  h("strong", guild.name || "Configured server"),
                  h("span", "ID: " + (guild.id || "—")),
                  guild.description ? h("span", { class: "discord-muted" }, guild.description) : null,
                ]),
              ]),
              h("div", { class: "discord-grid" }, [
                text("Members", guild.member_count), text("Online", guild.online_count), text("Verification", guild.verification_level),
                text("Boost tier", guild.premium_tier), text("Boosts", guild.premium_subscription_count), text("Locale", guild.preferred_locale),
                text("NSFW level", guild.nsfw_level), text("MFA level", guild.mfa_level), text("Owner ID", guild.owner_id), text("Vanity code", guild.vanity_url_code),
                text("AFK timeout", guild.afk_timeout ? guild.afk_timeout + " s" : "—"), text("Widget", guild.widget_enabled ? "Enabled" : "Disabled"),
                text("Explicit filter", guild.explicit_content_filter), text("Default notifications", guild.default_message_notifications),
              ]),
              features.length ? h("div", { class: "discord-chips" }, features.map(feature => badge(feature))) : null,
            ]),
            infoCard("Bot membership & permissions", [
              h("div", { class: "discord-grid" }, [
                text("Nickname", member.nickname), text("Joined server", member.joined_at ? new Date(member.joined_at).toLocaleString() : "—"),
                text("Pending", member.pending ? "Yes" : "No"), text("Role count", member.role_count), text("Permission value", member.permissions),
              ]),
              h("h4", "Roles"),
              roles.length ? h("div", { class: "discord-chips" }, roles.map(role => badge(role))) : h("span", { class: "discord-muted" }, "No roles returned."),
              h("h4", "Effective permissions"),
              permissions.length ? h("div", { class: "discord-chips" }, permissions.map(permission => badge(permission, permission === "ADMINISTRATOR"))) : h("span", { class: "discord-muted" }, "No permissions returned."),
            ]),
          ];

          const directoryCard = infoCard("Allowed notification channels and server users", [
            h("p", "Allow text or announcement channels for PUBLIC notifications. Removing a channel stops its deliveries immediately. Member linking is PRIVATE; only the host can verify a notification destination."),
            h("div", { class: "discord-actions" }, [h("button", { type: "button", disabled: busy.value, onClick: () => loadDirectory() }, "Load Discord directory")]),
            ...(directory.value ? [
              searchField("Find a channel", channelSearch, "Channel name or ID"),
              h("div", { class: "discord-actions" }, [
                h("button", { type: "button", disabled: busy.value, onClick: () => { allowedChannels.value = [...new Set([...allowedChannels.value, ...directory.value.channels.filter(channel => matches(channelSearch.value, channel.name, channel.id)).map(channel => channel.id)])]; } }, "Allow matching channels"),
                h("button", { type: "button", disabled: busy.value, onClick: () => { const visible = new Set(directory.value.channels.filter(channel => matches(channelSearch.value, channel.name, channel.id)).map(channel => channel.id)); allowedChannels.value = allowedChannels.value.filter(id => !visible.has(id)); } }, "Remove matching channels"),
              ]),
              h("p", { class: "discord-hint" }, allowedChannels.value.length + " channels selected; save below to apply."),
              h("div", { class: "discord-directory" }, directory.value.channels.filter(channel => matches(channelSearch.value, channel.name, channel.id)).map(channel => h("label", { class: "discord-channel-choice" }, [
                h("input", { type: "checkbox", checked: allowedChannels.value.includes(channel.id), disabled: busy.value,
                  onChange: event => { allowedChannels.value = event.target.checked ? [...allowedChannels.value, channel.id] : allowedChannels.value.filter(id => id !== channel.id); } }),
                h("span", "#" + channel.name), h("small", channel.id),
              ]))),
              h("div", { class: "discord-actions" }, [button("Save allowed channels", "allow-channels", () => ({ channel_ids: allowedChannels.value }))]),
              h("label", { class: "discord-field" }, [h("span", "Find a server user"), h("input", { value: memberSearch.value, onInput: event => { memberSearch.value = event.target.value; }, placeholder: "Username or display name" })]),
              h("label", { class: "discord-field" }, [h("span", "Discord member"), h("select", { value: memberSelection.value, disabled: busy.value, onChange: event => { memberSelection.value = event.target.value; } }, [
                h("option", { value: "" }, "Choose a Discord member"),
                ...directory.value.users.filter(user => matches(memberSearch.value, user.username, user.label, user.id)).map(user => h("option", { value: user.username }, user.label + " (@" + user.username + ") · " + user.id)),
              ])]),
              h("p", { class: "discord-hint" }, "Link the selected member to your signed-in app account. This does not verify access or change another app user's destinations."),
              h("div", { class: "discord-actions" }, [h("button", { type: "button", disabled: busy.value || !memberSelection.value, onClick: () => perform("link-private", { username: memberSelection.value }) }, "Link selected member to my account")]),
              directory.value.next_after ? h("div", { class: "discord-actions" }, [h("button", { type: "button", disabled: busy.value, onClick: () => loadDirectory(directory.value.next_after) }, "Load more server users")]) : null,
            ] : []),
          ]);
          const allowedChannelCard = infoCard("Your allowed notification channels", [
            h("p", "Choose an administrator-allowed channel, then add a Discord server channel destination in Notifications. Leave its channel ID blank to use this selection. Each destination keeps its chosen channel; use per-type routing to decide what it receives."),
            searchField("Find an allowed channel", channelSearch, "Channel name or ID"),
            h("label", { class: "discord-field" }, [h("span", "Default channel for new destinations"), h("select", { value: channelSelection.value, disabled: busy.value, onChange: event => { channelSelection.value = event.target.value; } }, [
              h("option", { value: "" }, "Choose an allowed channel"), ...channelChoices.value.filter(channel => channel.id === channelSelection.value || matches(channelSearch.value, channel.name, channel.id)).map(channel => h("option", { value: channel.id }, "#" + channel.name + " · " + channel.id)),
            ])]),
            h("div", { class: "discord-actions" }, [h("button", { type: "button", disabled: busy.value || !channelSelection.value, onClick: () => perform("select-channel", { channel_id: channelSelection.value }) }, "Use this channel for new destinations")]),
            channelChoices.value.length ? null : h("p", { class: "discord-hint" }, "An administrator has not allowed any channels yet."),
            h("p", { class: "discord-hint" }, "Channels remain PUBLIC and cannot receive recovery secrets or private/security notifications."),
          ]);

          const accounts = Array.isArray(c.accounts) ? c.accounts : [];
          const accountCards = accounts.filter(account => matches(accountSearch.value, account.global_name, account.username, account.discord_id)).map(account => infoCard(account.global_name || account.username || "Linked Discord account", [
            h("div", { class: "discord-identity" }, [
              image(account.avatar_url, account.username || "Discord account", "discord-avatar"),
              h("div", [
                h("strong", account.global_name || account.username || "Discord account"),
                h("span", "@" + (account.username || "—")),
                h("span", { class: "discord-muted" }, "Discord ID: " + (account.discord_id || "—")),
              ]),
              badge("Legacy profile link · PRIVATE", false),
            ]),
            h("div", { class: "discord-grid" }, [
              text("Linked", account.linked_at ? new Date(account.linked_at * 1000).toLocaleString() : "—"),
              text("Server nickname", account.server_nickname),
              text("Joined server", account.server_joined_at ? new Date(account.server_joined_at).toLocaleString() : "—"),
              text("Last test DM", account.last_test_at ? new Date(account.last_test_at * 1000).toLocaleString() : "Never"),
              text("Last notification", account.last_delivery_at ? new Date(account.last_delivery_at * 1000).toLocaleString() : "Never"),
            ]),
            c.link_warning ? h("p", { class: "discord-hint" }, c.link_warning) : null,
            h("div", { class: "discord-actions" }, [
              button("Send test DM", "test-dm", () => ({ discord_id: account.discord_id })),
              button("Unlink account", "unlink", () => ({ discord_id: account.discord_id }), true),
            ]),
          ]));

          const recoveryLabels = {
            eligible: "Ready for password-reset delivery",
            unsupported: "Recovery is not supported by this destination",
            provider_unavailable: "Provider unavailable; review installation, permissions and server configuration",
            destination_disabled: "Enable this destination and provider in Notifications",
            verification_required: "Verify this specific DM destination to enable recovery",
            sensitive_permission_required: "Grant the plugin sensitive-content permission for recovery",
            recovery_not_allowed: "Verified; allow recovery messages in Notifications",
            routing_disabled: "Password-reset routing disabled by preferences or server policy",
          };
          const destinationCards = destinations.value.filter(item => matches(accountSearch.value, item.username, item.discord_id, item.channel_id, item.kind, item.id, item.trust)).map(item => infoCard(
            item.username ? "@" + item.username : item.channel_id ? "Discord channel " + item.channel_id : item.kind === "discord_account_dm" ? "Discord account DM" : item.kind === "discord_bot_channel" ? "Discord server channel" : "Compatibility destination",
            [
              h("div", { class: "discord-identity" }, [h("strong", item.kind === "discord_account_dm" ? "Direct message destination" : item.kind === "discord_bot_channel" ? "PUBLIC server channel" : "Legacy grouped destination"), badge(item.trust, item.trust === "SECURE")]),
              h("p", { class: "discord-hint" }, item.active && item.enabled ? "Configured · Revision " + item.revision : "Inactive or disabled · Revision " + item.revision),
              h("p", { role: "status" }, recoveryLabels[item.recovery_status] || "Check recovery eligibility in Notifications"),
              h("div", { class: "discord-actions" }, [h("a", {
                href: notificationUrl(item.id, item.provider_id), class: "discord-notification-link",
              }, item.trust !== "SECURE" && item.kind === "discord_account_dm" ? "Verify DM and configure recovery" : item.recovery_status === "recovery_not_allowed" ? "Enable password-reset delivery" : "Manage this destination")]),
              item.recovery_status === "eligible" ? h("p", { class: "discord-hint" }, "Destination routing is ready. The administrator must also enable the password-reset plugin; the host rechecks all permissions and choices when sending.") : null,
            ],
          ));

          return h("section", { class: "discord-bot-settings" }, [
            h("div", { class: "discord-header" }, [
              h("div", [h("h2", admin ? "Discord bot administration" : "Your Discord connection"), h("p", admin ? "Everything the plugin can safely discover about the configured bot and server." : "PRIVATE DMs work before verification. Actual destination trust and password-reset routing below come from the host; verification and recovery choices are managed in Notifications.")]),
              h("button", { type: "button", disabled: loading.value || busy.value, onClick: refresh }, loading.value ? "Refreshing…" : "Refresh"),
            ]),
            loading.value ? h("p", { role: "status" }, "Loading Discord information…") : null,
            error.value ? h("p", { role: "alert", class: "discord-error" }, error.value) : null,
            message.value ? h("p", { role: "status", class: "discord-message" }, message.value) : null,
            ...(admin ? [
              infoCard("Compatibility bot and directory configuration", [
                h("p", c.bot_configured ? "The token is configured and never displayed back to the browser." : "No bot token configured."),
                field("Bot token (write-only)", tokenForm, "token", "password", "new-password"),
                h("div", { class: "discord-actions" }, [h("button", { type: "button", disabled: busy.value, onClick: () => loadServers() }, "Find bot servers")]),
                searchField("Find a server", serverSearch, "Server name or ID"),
                h("label", { class: "discord-field" }, [h("span", "Select a server joined by this bot"), h("select", { value: tokenForm.guild_id, disabled: busy.value, onChange: event => { tokenForm.guild_id = event.target.value; directory.value = null; } }, [
                  h("option", { value: "" }, "Choose a server"),
                  ...(tokenForm.guild_id && !servers.value.some(server => server.id === tokenForm.guild_id) ? [h("option", { value: tokenForm.guild_id }, "Current server · " + tokenForm.guild_id)] : []),
                  ...servers.value.filter(server => server.id === tokenForm.guild_id || matches(serverSearch.value, server.name, server.id)).map(server => h("option", { value: server.id }, server.name + " · " + server.id)),
                ])]),
                serverCursor.value ? h("button", { type: "button", disabled: busy.value, onClick: () => loadServers(serverCursor.value) }, "Load more servers") : null,
                field("Discord server ID (manual entry)", tokenForm, "guild_id", "text"),
                h("div", { class: "discord-actions" }, [button("Validate and save", "save-bot-config", () => ({ token: tokenForm.token, guild_id: tokenForm.guild_id })), button("Clear bot token", "clear-bot-token", () => ({}), true)]),
                h("p", { class: "discord-hint" }, "Server discovery uses the new token above or the stored compatibility token. Saving this section configures directory access and legacy grouped delivery. Per-account DMs and PUBLIC channels have separate, revision-bound provider settings below. Changing their server disables old destinations until explicitly configured again."),
                h("div", { class: "discord-actions" }, [
                  h("a", { href: notificationUrl(null, context.pluginId + ".account-dm", true) }, "Configure account DM provider"),
                  h("a", { href: notificationUrl(null, context.pluginId + ".channel", true) }, "Configure channel provider"),
                ]),
              ]),
              ...(c.configured ? [...adminCards, directoryCard] : [h("p", { class: "discord-hint" }, "Configure the bot above to inspect its Discord identity, server, membership, permissions and health.")]),
            ] : [
              h("a", { href: notificationUrl(null, context.pluginId + ".account-dm"), class: "discord-notification-link" }, "Add a DM destination or configure notification routing"),
              searchField("Find your destinations or linked accounts", accountSearch, "Username, channel, destination ID or trust"),
              destinationError.value ? h("p", { role: "alert", class: "discord-error" }, destinationError.value) : null,
              ...destinationCards,
              !destinationError.value && !destinations.value.length ? h("p", { class: "discord-hint" }, "No host notification destinations configured. Add a DM destination for ordinary PRIVATE delivery; verify it and allow recovery for password resets.") : null,
              destinationCursor.value ? h("button", { type: "button", onClick: () => loadDestinations(destinationCursor.value) }, "Load more destinations") : null,
              ...(accountCards.length ? [h("details", [h("summary", "Compatibility profile links (" + accounts.length + ")"), h("p", { class: "discord-hint" }, "These profile links belong to the legacy grouped PRIVATE provider. Optional profile verification does not establish host destination trust. Use actual destinations above for security and recovery."), ...accountCards])] : []),
              ...(c.configured ? [allowedChannelCard] : []),
              infoCard("Compatibility profile linking", [
                h("p", accounts.length ? "Add a compatibility profile link for the legacy grouped PRIVATE provider. Per-account destinations above each deliver to only their configured account." : "Enter your exact Discord username from the configured server. You can link it now for PRIVATE notifications; profile verification below is optional."),
                field("Discord username", userForm, "username", "text"),
                h("div", { class: "discord-actions" }, [button("Link for PRIVATE notifications", "link-private", () => ({ username: userForm.username })), button("Send optional profile verification code", "start-link", () => ({ username: userForm.username }))]),
                field("Eight-digit verification code", userForm, "code", "text", "one-time-code"),
                h("div", { class: "discord-actions" }, [button("Confirm optional profile code", "confirm-link", () => ({ code: userForm.code }))]),
                h("p", { class: "discord-hint" }, "Optional profile codes expire after ten minutes. This legacy grouped destination stays PRIVATE, even with profile proof. For recovery: configure Discord account DM in Notifications, complete the host challenge and enable recovery. The provider also needs the separate high-risk grant."),
              ]),
            ]),
          ]);
        };
      },
    });
  }

  context.registerComponent("admin", page(true));
  context.registerComponent("account", page(false));
}
