export function activate(context) {
  const { h, ref, reactive, defineComponent, onBeforeUnmount } = context.vue;
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
          try {
            config.value = await props.host.runAction("get-config");
            if (admin && !tokenForm.guild_id)
              tokenForm.guild_id = config.value.guild_id || "";
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
            message.value = result.message || "Saved.";
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
        refresh();
        return () => h("section", { class: "discord-bot-settings" }, [
          h("h2", admin ? "Discord bot administration" : "Link your Discord account"),
          h("p", admin
            ? "Configure the dedicated bot and the Discord server where users are members."
            : "Link a Discord account you control to receive private notifications."),
          loading.value ? h("p", { role: "status" }, "Loading settings…") : null,
          error.value ? h("p", { role: "alert", class: "discord-error" }, error.value) : null,
          message.value ? h("p", { role: "status", class: "discord-message" }, message.value) : null,
          ...(admin ? [
            h("section", { class: "discord-panel" }, [
              h("h3", "Bot configuration"),
              h("p", config.value.bot_configured
                ? "Configured bot: " + (config.value.bot_name || "Discord bot")
                : "No bot token configured."),
              field("Bot token (write-only)", tokenForm, "token", "password", "new-password"),
              field("Discord server ID", tokenForm, "guild_id", "text"),
              h("div", { class: "discord-actions" }, [
                button("Validate and save", "save-bot-config", () => ({
                  token: tokenForm.token,
                  guild_id: tokenForm.guild_id,
                })),
                button("Clear bot token", "clear-bot-token", () => ({}), true),
              ]),
              h("p", { class: "discord-hint" },
                "The bot must be in this server. Member search may require the Server Members Intent."),
            ]),
          ] : [
            h("section", { class: "discord-panel" }, [
              h("h3", config.value.linked
                ? "Linked to " + config.value.username
                : "Link a Discord username"),
              config.value.linked
                ? h("p", "Your Discord account has been verified. Notifications go only to this linked account.")
                : h("p", "Enter your exact Discord username from the configured server. A verification code will be sent by DM."),
              ...(!config.value.linked ? [
                field("Discord username", userForm, "username", "text"),
                button("Send verification code", "start-link", () => ({ username: userForm.username })),
                field("Eight-digit verification code", userForm, "code", "text", "one-time-code"),
                button("Verify and link", "confirm-link", () => ({ code: userForm.code })),
              ] : []),
              h("div", { class: "discord-actions" }, [
                ...(config.value.linked ? [
                  button("Send test DM", "test-dm"),
                  button("Unlink Discord account", "unlink", () => ({}), true),
                ] : []),
              ]),
            ]),
          ]),
        ]);
      },
    });
  }
  context.registerComponent("admin", page(true));
  context.registerComponent("account", page(false));
}
