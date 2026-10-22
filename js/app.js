(() => {
  const apiBase = window.FixFlowApiBase;
  const sessionKey = "fixflow_session";
  const app = document.querySelector("#main-content");
  const toastRegion = document.querySelector(".toast-region");
  let session = readSession();
  let tickets = [];
  let health = { open: 0, in_progress: 0, resolved: 0, high_priority: 0, unassigned: 0, active: 0 };
  let technicians = [];

  const esc = value => String(value || "").replace(/[&<>'\"]/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#039;", "\"":"&quot;" }[char]));
  const isStaff = () => ["warden", "admin"].includes(session?.user?.role);
  const isTechnician = () => session?.user?.role === "technician";
  const page = () => ["report", "resident", "admin", "technician"].includes(location.hash.slice(1)) ? location.hash.slice(1) : defaultPage();
  const defaultPage = () => session?.user?.role === "resident" ? "report" : session?.user?.role === "technician" ? "technician" : "admin";
  const statusClass = status => status === "In progress" ? "progress" : status.toLowerCase();
  const toast = text => { toastRegion.innerHTML = `<div class="toast">${esc(text)}</div>`; setTimeout(() => toastRegion.innerHTML = "", 4000); };

  function readSession() { try { return JSON.parse(sessionStorage.getItem(sessionKey)); } catch { return null; } }
  function saveSession(value) { session = value; sessionStorage.setItem(sessionKey, JSON.stringify(value)); }
  function logout(message = "Signed out.") { session = null; tickets = []; technicians = []; sessionStorage.removeItem(sessionKey); location.hash = ""; renderAuth(); if (message) toast(message); }
  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
    const response = await fetch(`${apiBase}${path}`, { ...options, headers });
    if (response.status === 401 && session) { logout("Session expired. Sign in again."); throw new Error("Session expired."); }
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Request failed.");
    return response.json();
  }
  async function load() {
    const calls = [api("/tickets")];
    if (isStaff()) calls.push(api("/analytics/service-health"), api("/users/technicians"));
    const result = await Promise.all(calls);
    tickets = result[0];
    health = isStaff() ? result[1] : { open: 0, in_progress: 0, resolved: 0, high_priority: 0, unassigned: 0, active: 0 };
    technicians = isStaff() ? result[2] : [];
  }
  function setNavigation() {
    const nav = document.querySelector(".nav");
    const profile = document.querySelector(".profile-button");
    if (!nav || !profile) return;
    const links = session.user.role === "resident" ? [["report", "Report"], ["resident", "My requests"]] : isTechnician() ? [["technician", "Technician"]] : [["admin", "Operations"]];
    nav.innerHTML = links.map(([route, label]) => `<a href="#${route}" data-route="${route}">${label}</a>`).join("");
    profile.textContent = "Sign out";
    profile.classList.add("signout-button");
    profile.setAttribute("aria-label", `Sign out ${session.user.display_name}`);
    profile.onclick = () => logout();
    nav.querySelectorAll("[data-route]").forEach(link => link.classList.toggle("active", link.dataset.route === page()));
  }
  function ticketCard(ticket, action = "") {
    return `<article class="ticket-card"><div class="ticket-top"><div><p class="ticket-id">${esc(ticket.id)} · ${esc(ticket.created_at)}</p><h3 class="ticket-title">${esc(ticket.category)} issue · Block ${esc(ticket.block)}, ${esc(ticket.room)}</h3></div><div class="pills"><span class="pill ${ticket.priority.toLowerCase()}">${esc(ticket.priority)}</span><span class="pill ${statusClass(ticket.status)}">${esc(ticket.status)}</span></div></div><p class="ticket-desc">${esc(ticket.description)}</p><div class="ticket-footer"><span class="ticket-meta">Assigned: ${esc(ticket.assignee)}</span>${ticket.duplicate_of ? `<span class="duplicate-note">Possible duplicate: ${esc(ticket.duplicate_of)}</span>` : ""}${action}</div></article>`;
  }
  function authView() {
    return `<section class="auth-shell"><section class="hero-copy"><p class="eyebrow">FixFlow secure workspace</p><h1>Maintenance work, safely routed.</h1><p class="lede">Residents report and track own issues. Hostel teams receive access through locally created staff accounts.</p><p class="auth-note">Public registration creates resident accounts only.</p></section><section class="panel auth-panel"><div class="auth-tabs"><button type="button" class="button secondary active-auth" data-auth-view="login">Sign in</button><button type="button" class="button secondary" data-auth-view="register">Register</button></div><div id="auth-form-slot"></div></section></section>`;
  }
  function authForm(view = "login") {
    const slot = document.querySelector("#auth-form-slot");
    if (!slot) return;
    slot.innerHTML = view === "register" ? `<form id="register-form" class="form-stack"><h2>Create resident account</h2><label>Full name<input name="display_name" autocomplete="name" required minlength="2" maxlength="80"></label><label>Email<input name="email" type="email" autocomplete="email" required></label><label>Password<input name="password" type="password" autocomplete="new-password" required minlength="10" placeholder="At least 10 characters"></label><button class="button" type="submit">Create resident account</button></form>` : `<form id="login-form" class="form-stack"><h2>Sign in</h2><label>Email<input name="email" type="email" autocomplete="email" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button class="button" type="submit">Sign in</button><p class="panel-subtitle">Staff accounts: use local bootstrap command from README.</p></form>`;
    document.querySelectorAll("[data-auth-view]").forEach(button => button.classList.toggle("active-auth", button.dataset.authView === view));
    slot.querySelector("form").addEventListener("submit", event => submitAuth(event, view));
  }
  async function submitAuth(event, view) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector("button");
    button.disabled = true; button.textContent = "Please wait…";
    try {
      const response = await api(`/auth/${view === "register" ? "register" : "login"}`, { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
      saveSession(response); await load(); location.hash = defaultPage(); render(); toast(`Signed in as ${response.user.display_name}.`);
    } catch (error) { toast(error.message); button.disabled = false; button.textContent = view === "register" ? "Create resident account" : "Sign in"; }
  }
  function reportView() {
    return `<section class="hero"><div class="hero-copy"><p class="eyebrow">Resident portal</p><h1>Get issue to right person, faster.</h1><p class="lede">Signed in as ${esc(session.user.display_name)}. FixFlow stores report, assigns ownership from account, keeps request private.</p></div><aside class="hero-card"><h2>What happens next</h2><div class="flow-step"><span class="flow-number">1</span><span><strong>Report</strong><br>Tell us what needs fixing.</span></div><div class="flow-step"><span class="flow-number">2</span><span><strong>Triage</strong><br>Staff receives queue.</span></div><div class="flow-step"><span class="flow-number">3</span><span><strong>Resolve</strong><br>Track work until done.</span></div></aside></section><section class="panel request-layout"><div><div class="panel-head"><div><h2>Report issue</h2><p class="panel-subtitle">Request belongs to your signed-in account.</p></div></div><form id="report-form" class="form-stack"><div class="field-grid"><label>Issue category<select name="category" required><option value="">Choose category</option>${window.FixFlowCategories.map(category => `<option>${category}</option>`).join("")}</select></label><label>Hostel block<select name="block" required><option value="">Select block</option><option>A</option><option>B</option><option>C</option><option>D</option></select></label><label>Room / location<input name="room" required></label></div><label>Describe issue<textarea name="description" required minlength="8" placeholder="Example: Paani leak ho raha hai below washroom sink since morning."></textarea></label><button class="button" type="submit">Submit maintenance request</button></form></div><aside class="intelligence-card"><h3>Secure Phase 2</h3><p>Backend ignores resident identity from browser. JWT account decides ticket owner and permissions.</p><ul class="rule-list"><li><span class="check">✓</span><span>Resident sees only own requests.</span></li><li><span class="check">✓</span><span>Staff assignment backend-enforced.</span></li><li><span class="check">✓</span><span>Expired tokens sign out safely.</span></li></ul></aside></section>`;
  }
  function residentView() {
    return `<section class="panel"><div class="panel-head"><div><p class="eyebrow">Resident portal</p><h2>My maintenance requests</h2><p class="panel-subtitle">Only requests owned by ${esc(session.user.display_name)}.</p></div><a class="button" href="#report">New request</a></div><div class="ticket-grid">${tickets.length ? tickets.map(ticket => ticketCard(ticket)).join("") : `<div class="empty">No requests yet. Report issue to begin.</div>`}</div></section>`;
  }
  function staffTicketAction(ticket) {
    const options = technicians.map(person => `<option value="${person.id}" ${ticket.assigned_to_id === person.id ? "selected" : ""}>${esc(person.display_name)}</option>`).join("");
    if (ticket.status === "Resolved") return `<button class="button small secondary" data-action="reopen" data-id="${ticket.id}">Reopen</button>`;
    if (!technicians.length) return `<span class="duplicate-note">Create technician locally first.</span>`;
    return `<span class="assignment"><select data-assignee="${ticket.id}"><option value="">Choose technician</option>${options}</select><button class="button small secondary" data-action="assign" data-id="${ticket.id}">${ticket.assigned_to_id ? "Reassign" : "Assign"}</button>${ticket.status === "In progress" ? `<button class="button small" data-action="resolve" data-id="${ticket.id}">Resolve</button>` : ""}</span>`;
  }
  function adminView() {
    return `<section><div class="panel-head"><div><p class="eyebrow">Operations dashboard</p><h1>Keep every issue moving.</h1><p class="panel-subtitle">${esc(session.user.role)} access. Assign technicians, update ticket workflow, review service health.</p></div></div><div class="stat-grid"><div class="stat-card"><div class="stat-label">Open</div><div class="stat-value">${health.open}</div><div class="stat-note">Needs assignment</div></div><div class="stat-card"><div class="stat-label">In progress</div><div class="stat-value">${health.in_progress}</div><div class="stat-note">Technician assigned</div></div><div class="stat-card"><div class="stat-label">Resolved</div><div class="stat-value">${health.resolved}</div><div class="stat-note">Saved in SQLite</div></div><div class="stat-card"><div class="stat-label">High priority</div><div class="stat-value">${health.high_priority}</div><div class="stat-note">Review first</div></div></div><div class="two-col"><section class="panel"><div class="panel-head"><div><h2>Incoming queue</h2><p class="panel-subtitle">Assignment validated by server.</p></div></div><div class="ticket-grid">${tickets.map(ticket => ticketCard(ticket, staffTicketAction(ticket))).join("")}</div></section><aside class="panel"><h2>Service health</h2><p class="panel-subtitle">Privileged analytics endpoint.</p><div class="metric-list"><div class="metric-row"><span>Resolved</span><strong>${health.resolved}</strong><div class="progress"><span style="width:${Math.min(100, health.resolved * 20)}%"></span></div></div><div class="metric-row"><span>Active</span><strong>${health.active}</strong><div class="progress"><span style="width:${Math.min(100, health.active * 18)}%"></span></div></div><div class="metric-row"><span>Unassigned</span><strong>${health.unassigned}</strong><div class="progress"><span style="width:${Math.min(100, health.unassigned * 25)}%"></span></div></div></div></aside></div></section>`;
  }
  function technicianView() {
    return `<section class="panel"><div class="panel-head"><div><p class="eyebrow">Technician workspace</p><h1>Assigned work</h1><p class="panel-subtitle">Only tickets assigned to ${esc(session.user.display_name)}. You can mark own work in progress or resolved.</p></div></div><div class="table-wrap"><table><thead><tr><th>Ticket</th><th>Location</th><th>Issue</th><th>Priority</th><th>Status</th><th>Action</th></tr></thead><tbody>${tickets.length ? tickets.map(ticket => `<tr><td>${ticket.id}</td><td>Block ${esc(ticket.block)}, ${esc(ticket.room)}</td><td>${esc(ticket.category)}</td><td><span class="pill ${ticket.priority.toLowerCase()}">${ticket.priority}</span></td><td>${ticket.status}</td><td>${ticket.status === "Resolved" ? "Resolved" : `<button class="button small" data-action="resolve" data-id="${ticket.id}">Mark resolved</button>`}</td></tr>`).join("") : `<tr><td colspan="6">No assigned tickets.</td></tr>`}</tbody></table></div></section>`;
  }
  function render() {
    if (!session) return renderAuth();
    const views = { report: reportView, resident: residentView, admin: adminView, technician: technicianView };
    app.innerHTML = views[page()](); setNavigation(); bind();
  }
  function renderAuth() {
    app.innerHTML = authView();
    const nav = document.querySelector(".nav"); if (nav) nav.innerHTML = "";
    const profile = document.querySelector(".profile-button"); if (profile) { profile.textContent = ""; profile.removeAttribute("aria-label"); profile.classList.remove("signout-button"); profile.onclick = null; }
    document.querySelectorAll("[data-auth-view]").forEach(button => button.addEventListener("click", () => authForm(button.dataset.authView)));
    authForm();
  }
  async function updateTicket(ticket, change) { await api(`/tickets/${ticket.id}`, { method: "PATCH", body: JSON.stringify(change) }); await load(); render(); }
  function bind() {
    const form = document.querySelector("#report-form");
    if (form) form.addEventListener("submit", async event => { event.preventDefault(); const button = form.querySelector("button"); button.disabled = true; button.textContent = "Submitting…"; try { const ticket = await api("/tickets", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) }); await load(); location.hash = "resident"; render(); toast(ticket.duplicate_of ? `Request ${ticket.id} submitted; duplicate ${ticket.duplicate_of} flagged.` : `Request ${ticket.id} submitted.`); } catch (error) { toast(error.message); button.disabled = false; button.textContent = "Submit maintenance request"; } });
    document.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", async () => { const ticket = tickets.find(item => item.id === button.dataset.id); if (!ticket) return; try { if (button.dataset.action === "assign") { const chosen = document.querySelector(`[data-assignee="${ticket.id}"]`)?.value; if (!chosen) throw new Error("Choose technician first."); await updateTicket(ticket, { assignee_id: Number(chosen), status: "In progress" }); toast(`${ticket.id} assigned.`); } else if (button.dataset.action === "reopen") { await updateTicket(ticket, { status: "Open" }); toast(`${ticket.id} reopened.`); } else { await updateTicket(ticket, { status: "Resolved" }); toast(`${ticket.id} marked resolved.`); } } catch (error) { toast(error.message); } }));
  }
  async function start() {
    if (!session) return renderAuth();
    try { const user = await api("/auth/me"); session.user = user; saveSession(session); await load(); render(); }
    catch (error) { if (session) logout(""); }
  }
  window.addEventListener("hashchange", () => session && render());
  start();
})();
