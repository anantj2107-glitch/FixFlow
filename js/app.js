(() => {
  const apiBase = window.FixFlowApiBase;
  const app = document.querySelector("#main-content");
  const toastRegion = document.querySelector(".toast-region");
  const residentName = "Aarav Kumar";
  let tickets = [];
  let health = { open: 0, in_progress: 0, resolved: 0, high_priority: 0, unassigned: 0, active: 0 };

  const esc = value => String(value || "").replace(/[&<>'\"]/g, char => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#039;", "\"":"&quot;" }[char]));
  const page = () => ["report", "resident", "admin", "technician"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "report";
  const statusClass = status => status === "In progress" ? "progress" : status.toLowerCase();
  const showToast = text => { toastRegion.innerHTML = `<div class="toast">${esc(text)}</div>`; setTimeout(() => toastRegion.innerHTML = "", 4000); };
  async function api(path, options = {}) {
    const response = await fetch(`${apiBase}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || "Request failed.");
    return response.json();
  }
  async function load() { [tickets, health] = await Promise.all([api("/tickets"), api("/analytics/service-health")]); }
  function ticketCard(ticket, action = "") {
    return `<article class="ticket-card"><div class="ticket-top"><div><p class="ticket-id">${esc(ticket.id)} · ${esc(ticket.created_at)}</p><h3 class="ticket-title">${esc(ticket.category)} issue · Block ${esc(ticket.block)}, ${esc(ticket.room)}</h3></div><div class="pills"><span class="pill ${ticket.priority.toLowerCase()}">${esc(ticket.priority)}</span><span class="pill ${statusClass(ticket.status)}">${esc(ticket.status)}</span></div></div><p class="ticket-desc">${esc(ticket.description)}</p><div class="ticket-footer"><span class="ticket-meta">Assigned: ${esc(ticket.assignee)}</span>${ticket.duplicate_of ? `<span class="duplicate-note">Possible duplicate: ${esc(ticket.duplicate_of)}</span>` : ""}${action}</div></article>`;
  }
  function reportView() {
    return `<section class="hero"><div class="hero-copy"><p class="eyebrow">Hostel maintenance, made visible</p><h1>Get issues to the right person, faster.</h1><p class="lede">FixFlow saves each report in a real local database, creates a clear operations queue, and keeps residents updated from request to resolution.</p></div><aside class="hero-card"><h2>What happens next</h2><div class="flow-step"><span class="flow-number">1</span><span><strong>Report</strong><br>Tell us what needs fixing.</span></div><div class="flow-step"><span class="flow-number">2</span><span><strong>Triage</strong><br>FixFlow suggests a priority.</span></div><div class="flow-step"><span class="flow-number">3</span><span><strong>Resolve</strong><br>Track work until done.</span></div></aside></section><section class="panel request-layout"><div><div class="panel-head"><div><h2>Report an issue</h2><p class="panel-subtitle">Your request is saved by FixFlow's local backend.</p></div></div><form id="report-form" class="form-stack"><div class="field-grid"><label>Issue category<select name="category" required><option value="">Choose a category</option>${window.FixFlowCategories.map(category => `<option>${category}</option>`).join("")}</select></label><label>Hostel block<select name="block" required><option value="">Select block</option><option>A</option><option>B</option><option>C</option><option>D</option></select></label><label>Room / location<input name="room" placeholder="Example: 204 or Ground-floor lobby" required></label><label>Your name<input name="resident" value="${residentName}" required></label></div><label>Describe the issue<textarea name="description" placeholder="Example: Paani leak ho raha hai below the washroom sink since morning." required></textarea></label><button class="button" type="submit">Submit maintenance request</button></form></div><aside class="intelligence-card"><h3>V2: real data flow</h3><p>The app now sends reports to FastAPI and persists them in SQLite.</p><ul class="rule-list"><li><span class="check">✓</span><span><strong>Priority:</strong> safety language gets a high-priority suggestion.</span></li><li><span class="check">✓</span><span><strong>Duplicates:</strong> active reports in the same block are flagged for review.</span></li><li><span class="check">✓</span><span><strong>Next:</strong> measured multilingual embeddings replace rule matching.</span></li></ul></aside></section>`;
  }
  function residentView() {
    const mine = tickets.filter(ticket => ticket.resident === residentName);
    return `<section class="panel"><div class="panel-head"><div><p class="eyebrow">Resident portal</p><h2>My maintenance requests</h2><p class="panel-subtitle">Showing saved requests for ${residentName}. Login arrives in the next security stage.</p></div><a class="button" href="#report">New request</a></div><div class="ticket-grid">${mine.length ? mine.map(ticket => ticketCard(ticket)).join("") : `<div class="empty">No requests yet. Report an issue to begin.</div>`}</div></section>`;
  }
  const actionLabel = ticket => ticket.status === "Open" ? "Assign" : ticket.status === "In progress" ? "Resolve" : "Reopen";
  const ticketActions = records => records.map(ticket => ticketCard(ticket, `<button class="button small secondary" data-action="advance" data-id="${ticket.id}">${actionLabel(ticket)}</button>`)).join("");
  function adminView() {
    return `<section><div class="panel-head"><div><p class="eyebrow">Operations dashboard</p><h1>Keep every issue moving.</h1><p class="panel-subtitle">Prioritize incoming reports, assign work, and keep residents informed.</p></div></div><div class="stat-grid"><div class="stat-card"><div class="stat-label">Open requests</div><div class="stat-value">${health.open}</div><div class="stat-note">Needs assignment</div></div><div class="stat-card"><div class="stat-label">In progress</div><div class="stat-value">${health.in_progress}</div><div class="stat-note">Technician assigned</div></div><div class="stat-card"><div class="stat-label">Resolved</div><div class="stat-value">${health.resolved}</div><div class="stat-note">Persisted in SQLite</div></div><div class="stat-card"><div class="stat-label">High priority</div><div class="stat-value">${health.high_priority}</div><div class="stat-note">Review first</div></div></div><div class="two-col"><section class="panel"><div class="panel-head"><div><h2>Incoming queue</h2><p class="panel-subtitle">Every action updates the shared API and database.</p></div><div class="toolbar"><select id="status-filter"><option value="All">All statuses</option><option>Open</option><option>In progress</option><option>Resolved</option></select><select id="priority-filter"><option value="All">All priorities</option><option>High</option><option>Medium</option><option>Low</option></select></div></div><div id="admin-tickets" class="ticket-grid">${ticketActions(tickets)}</div></section><aside class="panel"><h2>Service health</h2><p class="panel-subtitle">Live totals returned by the persisted queue.</p><div class="metric-list"><div class="metric-row"><span>Resolved requests</span><strong>${health.resolved}</strong><div class="progress"><span style="width:${Math.min(100, health.resolved * 20)}%"></span></div></div><div class="metric-row"><span>Active requests</span><strong>${health.active}</strong><div class="progress"><span style="width:${Math.min(100, health.active * 18)}%"></span></div></div><div class="metric-row"><span>Unassigned work</span><strong>${health.unassigned}</strong><div class="progress"><span style="width:${Math.min(100, health.unassigned * 25)}%"></span></div></div></div></aside></div></section>`;
  }
  function technicianView() {
    const assigned = tickets.filter(ticket => ticket.assignee !== "Unassigned" && ticket.status !== "Resolved");
    return `<section class="panel"><div class="panel-head"><div><p class="eyebrow">Technician workspace</p><h1>Today’s assigned work</h1><p class="panel-subtitle">A focused queue connected to the same shared database.</p></div></div><div class="table-wrap"><table><thead><tr><th>Ticket</th><th>Location</th><th>Issue</th><th>Priority</th><th>Assigned to</th><th>Action</th></tr></thead><tbody>${assigned.length ? assigned.map(ticket => `<tr><td>${ticket.id}</td><td>Block ${ticket.block}, ${ticket.room}</td><td>${ticket.category}</td><td><span class="pill ${ticket.priority.toLowerCase()}">${ticket.priority}</span></td><td>${ticket.assignee}</td><td><button class="button small" data-action="resolve" data-id="${ticket.id}">Mark resolved</button></td></tr>`).join("") : `<tr><td colspan="6">No active work assigned.</td></tr>`}</tbody></table></div></section>`;
  }
  function render() {
    const views = { report: reportView, resident: residentView, admin: adminView, technician: technicianView };
    app.innerHTML = views[page()]();
    document.querySelectorAll("[data-route]").forEach(link => link.classList.toggle("active", link.dataset.route === page()));
    bind();
  }
  async function progress(ticket, forcedResolve = false) {
    const change = forcedResolve || ticket.status === "In progress" ? { status: "Resolved" } : ticket.status === "Resolved" ? { status: "Open", assignee: "Unassigned" } : { status: "In progress", assignee: ticket.category === "Internet" ? "Priya Nair" : "Rohan Singh" };
    await api(`/tickets/${ticket.id}`, { method: "PATCH", body: JSON.stringify(change) });
    await load(); render();
    showToast(change.status === "Resolved" ? `${ticket.id} marked resolved.` : change.status === "Open" ? `${ticket.id} reopened.` : `${ticket.id} assigned to ${change.assignee}.`);
  }
  function bind() {
    const form = document.querySelector("#report-form");
    if (form) form.addEventListener("submit", async event => { event.preventDefault(); const button = form.querySelector("button"); button.disabled = true; button.textContent = "Submitting…"; try { const ticket = await api("/tickets", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) }); await load(); location.hash = "resident"; render(); showToast(ticket.duplicate_of ? `Request ${ticket.id} submitted; ${ticket.duplicate_of} was flagged for review.` : `Request ${ticket.id} submitted.`); } catch (error) { showToast(error.message); button.disabled = false; button.textContent = "Submit maintenance request"; } });
    document.querySelectorAll("[data-action]").forEach(button => button.addEventListener("click", async () => { const ticket = tickets.find(item => item.id === button.dataset.id); if (!ticket) return; try { await progress(ticket, button.dataset.action === "resolve"); } catch (error) { showToast(error.message); } }));
    const status = document.querySelector("#status-filter"), priority = document.querySelector("#priority-filter");
    [status, priority].filter(Boolean).forEach(control => control.addEventListener("change", () => { const shown = tickets.filter(ticket => (status.value === "All" || ticket.status === status.value) && (priority.value === "All" || ticket.priority === priority.value)); document.querySelector("#admin-tickets").innerHTML = shown.length ? ticketActions(shown) : `<div class="empty">No requests match these filters.</div>`; bind(); }));
  }
  async function start() { try { await load(); render(); } catch (error) { app.innerHTML = `<section class="panel"><h1>FixFlow could not connect to the backend.</h1><p class="lede">Start the FastAPI server, then refresh this page. ${esc(error.message)}</p></section>`; } }
  window.addEventListener("hashchange", render);
  start();
})();
