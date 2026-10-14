export function activate(context) {
  const { h, ref, defineComponent } = context.vue;
  context.registerComponent("admin", defineComponent({
    props: ["host"],
    setup(props) {
      const people = ref([]), cursor = ref(null), busy = ref(false), error = ref(""), message = ref("");
      const pending = ref(null), confirmed = ref(false);
      async function load(next = false) {
        busy.value = true; error.value = "";
        try {
          const result = await props.host.runAction("admin-list", next && cursor.value ? {cursor: cursor.value} : {});
          people.value = next ? [...people.value, ...result.participants] : result.participants;
          cursor.value = result.next_cursor;
        } catch (err) { error.value = err.message; }
        finally { busy.value = false; }
      }
      function choose(operation, person, source) {
        pending.value = {operation, ...(person ? {actor_id: person.id} : {all: true}), ...(source ? {source_id: source.id} : {}),
          label: person ? (person.username || person.display_name) + (source ? " · " + source.origin : "") : "all saved Game Night participants and rooms"};
        confirmed.value = false;
      }
      async function apply() {
        if (!confirmed.value || !pending.value) return;
        busy.value = true; error.value = "";
        try {
          const {label, ...values} = pending.value;
          await props.host.runAction("admin-manage", {...values, confirmed: true});
          message.value = (values.operation === "purge" ? "Purged " : "Unlinked ") + label;
          pending.value = null; confirmed.value = false; await load();
        } catch (err) { error.value = err.message; }
        finally { busy.value = false; }
      }
      load();
      const button = (text, action, danger = false) => h("button", {type:"button", disabled:busy.value, class:danger ? "gn-danger" : "", onClick:action}, text);
      return () => h("div", {class:"gn-admin"}, [
        h("h2", "Game Night participants"),
        h("p", "A guest is signed in through Discord but has no connected tracking library. Linked users have approved source connections; this does not create or merge tracking accounts."),
        h("p", "Unlink removes saved broker connections and signs this participant out. Purge also removes their Activity identity and room inputs. Tracking libraries and source-side grants are kept; revoke those in the source's Connected apps."),
        h("div", {class:"gn-actions"}, [button("Refresh participants", () => load()), button("Purge all Activity data", () => choose("purge"), true)]),
        error.value ? h("p", {role:"alert",class:"gn-error"}, error.value) : null,
        message.value ? h("p", {role:"status"}, message.value) : null,
        pending.value ? h("section", {class:"gn-confirm", "aria-label":"Confirm participant management"}, [
          h("h3", (pending.value.operation === "purge" ? "Purge " : "Unlink ") + pending.value.label + "?"),
          h("p", pending.value.operation === "purge" ? "This permanently removes the selected Activity data. Other participants' libraries are preserved; affected shortlists and shared selection history are cleared." : "Saved connection credentials are forgotten and the participant must sign in again. Their self-reported guest games remain."),
          h("label", [h("input", {type:"checkbox", checked:confirmed.value, onChange:e=>confirmed.value=e.target.checked}), " I confirm this action"]),
          h("div", {class:"gn-actions"}, [h("button", {type:"button", class:"gn-danger", disabled:busy.value || !confirmed.value, onClick:apply}, "Confirm " + pending.value.operation), button("Cancel", ()=>pending.value=null)])
        ]) : null,
        ...people.value.map(person => h("article", {key:person.id,class:"gn-person"}, [
          h("h3", person.username ? "@" + person.username : person.display_name),
          h("p", person.display_name + " · Discord ID: " + person.subject),
          h("p", (person.sources.some(source=>source.state === "connected") ? "Library linked" : "Guest / no active library") + " · Identity retention until " + new Date(person.expires_at * 1000).toLocaleString()),
          ...person.sources.map(source => h("div", {class:"gn-source"}, [h("span", source.origin + " · " + source.state), button("Unlink this connection", ()=>choose("unlink", person, source))])),
          h("div", {class:"gn-actions"}, [button("Unlink all connections", ()=>choose("unlink",person)), button("Purge participant data", ()=>choose("purge",person), true)])
        ])),
        !people.value.length && !busy.value ? h("p", "No saved participants.") : null,
        cursor.value ? button("Load more participants", ()=>load(true)) : null,
        h("p", "Set room/guest retention under Administration → Integration access (up to 365 days). Valid remembered source grants may outlive room retention. Retroactive account merging is tracked separately; reconnect under the intended source account instead.")
      ]);
    }
  }));
}
