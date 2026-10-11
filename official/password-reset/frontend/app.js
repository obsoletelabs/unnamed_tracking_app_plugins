const el = id => document.getElementById(id);
let registered = false;
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
function resize() { request("plugin.resize", {height:document.documentElement.scrollHeight + 20}).catch(()=>{}); }
async function refresh() {
 const state=await action("status"); registered=state.registered===true;
 el("status").textContent=registered ? "Account recovery enabled" : "Account recovery disabled";
 el("status").className=""; el("lifetime").value=state.token_lifetime_seconds;
 el("enable").disabled=false; el("disable").disabled=!registered; resize();
}
async function run(button, operation) {
 button.disabled=true;
 try {await operation();await refresh();} catch(error) {el("status").textContent=error.message;el("status").className="error";}
 finally {button.disabled=button.id==="disable"&&!registered;resize();}
}
el("enable").onclick=()=>{if(el("configuration").reportValidity())run(el("enable"),()=>action("enable",{token_lifetime_seconds:Number(el("lifetime").value)}));};
el("disable").onclick=()=>run(el("disable"),()=>action("disable"));
el("configuration").onkeydown=event=>{if(event.key==="Enter"&&!event.isComposing){event.preventDefault();el("enable").click();}};
refresh().catch(error=>{el("status").textContent=error.message;el("status").className="error";resize();});
