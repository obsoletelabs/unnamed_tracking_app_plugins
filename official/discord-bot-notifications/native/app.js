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
        let live = true;
        onBeforeUnmount(() => { live = false; });

        async function refresh() {
          loading.value = true;
          error.value = "";
          const started = performance.now();
          try {
            const result = await props.host.runAction("get-config");
            if (!live) return;
            config.value = { ...result, browser_refresh_ms: Math.round(performance.now() - started) };
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
          const linked = c.linked;
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
              h("div", { class: "discord-grid" }, [
                text("API health", c.health?.api_ok === false ? "Unavailable" : "Healthy"),
                text("Plugin request", c.health?.request_ms ? c.health.request_ms + " ms" : "—"),
                text("Browser refresh", c.browser_refresh_ms ? c.browser_refresh_ms + " ms" : "—"),
                text("Verified bot", bot.verified === true ? "Yes" : bot.verified === false ? "No" : "Unknown"),
              ]),
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
                text("Members", guild.member_count),
                text("Online", guild.online_count),
                text("Verification", guild.verification_level),
                text("Boost tier", guild.premium_tier),
                text("Locale", guild.preferred_locale),
                text("NSFW level", guild.nsfw_level),
                text("Owner ID", guild.owner_id),
                text("Vanity code", guild.vanity_url_code),
              ]),
              features.length ? h("div", { class: "discord-chips" }, features.map(feature => badge(feature))) : null,
            ]),
            infoCard("Bot membership & permissions", [
              h("div", { class: "discord-grid" }, [
                text("Nickname", member.nickname),
                text("Joined server", member.joined_at ? new Date(member.joined_at).toLocaleString() : "—"),
                text("Pending", member.pending ? "Yes" : "No"),
                text("Role count", member.role_count),
                text("Permission value", member.permissions),
              ]),
              h("h4", "Roles"),
              roles.length ? h("div", { class: "discord-chips" }, roles.map(role => badge(role))) : h("span", { class: "discord-muted" }, "No roles returned."),
              h("h4", "Permissions returned by Discord"),
              permissions.length ? h("div", { class: "discord-chips" }, permissions.map(permission => badge(permission, permission === "ADMINISTRATOR"))) : h("span", { class: "discord-muted" }, "No permissions returned."),
            ]),
          ];

          const accountCards = linked ? [
            infoCard("Verified Discord account", [
              h("div", { class: "discord-identity" }, [
                image(c.avatar_url, c.username || "Discord account", "discord-avatar"),
                h("div", [
                  h("strong", c.global_name || c.username || "Discord account"),
                  h("span", "@" + (c.username || "—")),
                  h("span", { class: "discord-muted" }, "Discord ID: " + (c.discord_id || "—")),
                ]),
                badge("Verified", true),
              ]),
              h("div", { class: "discord-grid" }, [
                text("Linked", c.linked_at ? new Date(c.linked_at * 1000).toLocaleString() : "—"),
                text("Server nickname", c.server_nickname),
                text("Joined server", c.server_joined_at ? new Date(c.server_joined_at).toLocaleString() : "—"),
              ]),
              c.link_warning ? h("p", { class: "discord-hint" }, c.link_warning) : null,
              h("div", { class: "discord-actions" }, [button("Refresh Discord details", "get-config"), button("Send test DM", "test-dm"), button("Unlink Discord account", "unlink", () => ({}), true)]),
            ]),
          ] : [];

          return h("section", { class: "discord-bot-settings" }, [
            h("div", { class: "discord-header" }, [
              h("div", [h("h2", admin ? "Discord bot administration" : "Your Discord connection"), h("p", admin ? "Everything the plugin can safely discover about the configured bot and server." : "A verified Discord account for private notification delivery.")]),
              h("button", { type: "button", disabled: loading.value || busy.value, onClick: refresh }, loading.value ? "Refreshing…" : "Refresh"),
            ]),
            loading.value ? h("p", { role: "status" }, "Loading Discord information…") : null,
            error.value ? h("p", { role: "alert", class: "discord-error" }, error.value) : null,
            message.value ? h("p", { role: "status", class: "discord-message" }, message.value) : null,
            ...(admin ? [
              infoCard("Bot configuration", [
                h("p", c.bot_configured ? "The token is configured and never displayed back to the browser." : "No bot token configured."),
                field("Bot token (write-only)", tokenForm, "token", "password", "new-password"),
                field("Discord server ID", tokenForm, "guild_id", "text"),
                h("div", { class: "discord-actions" }, [
                  button("Validate and save", "save-bot-config", () => ({ token: tokenForm.token, guild_id: tokenForm.guild_id })),
                  button("Clear bot token", "clear-bot-token", () => ({}), true),
                ]),
                h("p", { class: "discord-hint" }, "The bot must be a member of this server. Member lookup may require the Server Members Intent."),
              ]),
              ...(c.configured ? adminCards : [h("p", { class: "discord-hint" }, "Configure the bot above to inspect its Discord identity, server, membership, permissions and health.")]),
            ] : [
              ...(linked ? accountCards : [
                infoCard("Link your Discord account", [
                  h("p", "Enter your exact Discord username from the configured server. The bot sends an eight-digit code by DM; only the account that receives the code can be linked."),
                  field("Discord username", userForm, "username", "text"),
                  h("div", { class: "discord-actions" }, [button("Send verification code", "start-link", () => ({ username: userForm.username }))]),
                  field("Eight-digit verification code", userForm, "code", "text", "one-time-code"),
                  h("div", { class: "discord-actions" }, [button("Verify and link", "confirm-link", () => ({ code: userForm.code }))]),
                  h("p", { class: "discord-hint" }, "Codes expire after ten minutes and failed verification attempts are limited."),
                ]),
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
