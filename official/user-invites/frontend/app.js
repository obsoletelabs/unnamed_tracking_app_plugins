const el = id => document.getElementById(id);
let registered = false;
const invitationPage=new URLSearchParams(window.location.search).get("page")==="invite";
el("configuration").hidden=invitationPage;
el("send").hidden=!invitationPage;
document.querySelector("section").hidden=!invitationPage;
if(invitationPage) document.querySelector("h1").textContent="Invite user";
function request(method, payload = {}) {
 return new Promise((resolve, reject) => {
  const requestId = crypto.randomUUID();
  const timeout = setTimeout(() => { window.removeEventListener("message", receive); reject(new Error("The host did not respond.")); }, 30000);
  function receive(event) {
   if(event.source !== window.parent || event.data?.type !== "plugin-api-response" || event.data.requestId !== requestId) return;
   clearTimeout(timeout); window.removeEventListener("message", receive);
   event.data.error ? reject(new Error(event.data.error)) : resolve(event.data.result || {});
  }
  window.addEventListener("message", receive);
  window.parent.postMessage({type:"plugin-api-request",requestId,method,payload}, "*");
 });
}
const action = (actionId, values={}) => request("plugin.run-action", {actionId,values});
const when = value => new Date(value * 1000).toLocaleString();
function resize() { request("plugin.resize", {height:document.documentElement.scrollHeight + 20}).catch(()=>{}); }
async function refresh() {
 const state = await action("status");
 registered = state.registered === true;
 el("lifetime").value = state.token_lifetime_seconds;
 el("enable").disabled = false;
 el("issue").disabled = !registered;
 el("disable").disabled = !registered;
 el("status").textContent = registered ? "Invitations enabled" : "Invitations disabled";
 el("status").className = "";
 const rows = registered && invitationPage ? (await action("list-invites")).invitations : [];
 el("invitations").replaceChildren();
 if(!rows.length) el("invitations").textContent = registered ? "No recent invitations." : "Enable invitations in Administration â†’ Account security â†’ User invitations before sending.";
 for(const row of rows) {
  const article=document.createElement("article"), address=document.createElement("strong"), info=document.createElement("p");
  address.textContent=row.email;
  info.textContent=`${row.status} Ã‚Â· Delivery: ${row.delivery_status || "unavailable"} Ã‚Â· Expires ${when(row.expires_at)}`;
  article.append(address,info);
  if(row.status === "pending") {
   const button=document.createElement("button"); button.type="button"; button.textContent="Revoke invitation";
   button.onclick=()=>run(button,async()=>{await action("revoke",{id:row.id});await refresh();}); article.append(button);
  }
  el("invitations").append(article);
 }
 resize();
}
async function run(button, callback) {
 button.disabled=true;
 try {await callback();} catch(error) {el("status").textContent=error.message;el("status").className="error";}
 finally {button.disabled=(button.id==="issue"||button.id==="disable")&&!registered;resize();}
}
// Opaque host iframes intentionally forbid native form navigation. Use the
// public action bridge for both pointer and Enter-key activation.
function control(formId, buttonId, callback) {
 const form=el(formId), button=el(buttonId);
 button.onclick=()=>{if(form.reportValidity())run(button,callback);};
 form.onkeydown=event=>{if(event.key==="Enter"&&!event.isComposing){event.preventDefault();button.click();}};
}
control("configuration","enable",async()=>{await action("enable",{token_lifetime_seconds:Number(el("lifetime").value)});await refresh();});
el("disable").onclick=event=>run(event.target,async()=>{await action("disable");await refresh();});
control("send","issue",async()=>{await action("issue",{email:el("email").value.trim()});el("email").value="";await refresh();el("status").textContent="Invitation queued. Delivery status appears below.";});
el("refresh").onclick=event=>run(event.target,refresh);
refresh().catch(error=>{el("status").textContent=error.message;el("status").className="error";});
