"use strict";

const local = location.hostname === "127.0.0.1" && location.pathname === "/private/";
const demoVersion = "synthetic-m6-v1";
const storageKey = "davao-observatory:synthetic-m6-v1:reviews";
const modes = {PUJ: "Jeepney", PUB: "Bus", UV_EXPRESS: "UV Express"};
const colors = {PUJ: "#09716b", PUB: "#22559f", UV_EXPRESS: "#9e4d19"};
const decisions = {keep_unresolved: "Keep unresolved", request_evidence: "Request evidence", document_review: "Document review"};
const fixtures = [
  ["A", "Demo jeepney corridor", "PUJ", "EXISTING", [[125.55, 7.05], [125.57, 7.08], [125.62, 7.09]]],
  ["B", "Demo bus corridor", "PUB", "IRIP", [[125.56, 7.11], [125.59, 7.085], [125.63, 7.11]]],
  ["C", "Demo UV Express corridor", "UV_EXPRESS", "EXISTING", [[125.56, 7.06], [125.60, 7.06], [125.64, 7.07]]],
  ["D", "Demo record awaiting linework", "PUB", "EXISTING", null],
];
const demoRoutes = fixtures.map(([id, name, mode, classification, line]) => ({
  route_id: id, route_name: name, mode, classification, metadata_status: "synthetic record",
  source_status: line ? "synthetic line supplied" : "synthetic line missing",
  source_record_id: "synthetic fixture " + id, file_id: "demo-file-" + id,
  directions: [{ordinal: 1, direction: "Demo outbound", association_status: "unresolved",
    reason: "Training case for documenting the evidence needed to match a direction."}],
  cases: [{issue_id: "demo-" + id, code: "unresolved_geometry_association",
    severity: "review", detail: "Direction identity needs supporting evidence."}],
}));
const demoFeatures = fixtures.filter(entry => entry[4]).map(([id, , , , coordinates]) => ({
  id: "demo-line-" + id, geometry: {type: "LineString", coordinates},
  properties: {route_ids: [id], status: "synthetic line", candidate_route_ids: [], file_id: "demo-file-" + id},
}));

const byId = id => document.getElementById(id);
const state = {routes: [], features: [], areas: [], selected: null, selectedLine: null,
  bounds: null, case: null, extent: null, routeCount: 30, caseCount: 20, active: null,
  filters: {}, generation: 0, areaGeneration: 0, selection: 0, caseSelection: 0};

function node(tag, text, target) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (target) target.append(element);
  return element;
}

function button(target, text, action) {
  const element = node("button", text, target);
  element.type = "button";
  element.addEventListener("click", () => Promise.resolve().then(action).catch(showError));
  return element;
}

function notify(message, error = false) {
  const notice = byId("notice");
  notice.textContent = message;
  notice.classList.toggle("error", error);
}

const showError = error => notify(error.message || "The operation failed.", true);
const display = value => String(value ?? "Unknown").replaceAll("_", " ");
const lines = feature => feature.geometry.type === "LineString" ? [feature.geometry.coordinates] : feature.geometry.coordinates;

async function call(path, query = {}, payload) {
  const params = new URLSearchParams(query);
  let response;
  try { response = await fetch("/api/" + path + (params.size ? "?" + params : ""), payload ? {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
  } : {}); } catch { throw new Error("Local API unavailable. Check that the private server is running and its release verification succeeded, then reload. Your entered note is retained."); }
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}

async function collect(path, query, key) {
  const records = [];
  for (let offset = 0; offset < 10000;) {
    const page = await call(path, {...query, limit: 100, offset});
    records.push(...page[key]);
    if (!page[key].length || records.length >= page.total) return {records, summary: page};
    offset += page[key].length;
  }
  throw new Error("The result exceeds the map’s display limit. Apply a narrower filter.");
}

function includesRoute(route, filters) {
  return (!filters.mode || route.mode === filters.mode) &&
    (!filters.classification || route.classification === filters.classification) &&
    (!filters.q || (route.route_id + " " + route.route_name).toLowerCase().includes(filters.q.toLowerCase()));
}

function boundsFrom(text) {
  const tokens = text.split(",");
  if (tokens.length !== 4 || tokens.some(token => !token.trim())) throw new Error("Enter west, south, east and north.");
  const values = tokens.map(Number);
  const [w, s, e, n] = values;
  if (!values.every(Number.isFinite) || !(w >= -180 && w < e && e <= 180 && s >= -90 && s < n && n <= 90)) {
    throw new Error("Use ordered longitude and latitude values.");
  }
  return values;
}

// Clip a segment parametrically against a closed rectangle, including boundary touches.
function touches(a, b, bounds) {
  let lower = 0, upper = 1;
  for (let axis = 0; axis < 2; axis++) {
    const delta = b[axis] - a[axis];
    if (!delta) {
      if (a[axis] < bounds[axis] || a[axis] > bounds[axis + 2]) return false;
      continue;
    }
    const left = (bounds[axis] - a[axis]) / delta, right = (bounds[axis + 2] - a[axis]) / delta;
    lower = Math.max(lower, Math.min(left, right));
    upper = Math.min(upper, Math.max(left, right));
    if (upper < lower) return false;
  }
  return true;
}

const demoIntersects = (feature, bounds) => lines(feature).some(line =>
  line.some((point, index) => index > 0 && touches(line[index - 1], point, bounds)));

function overview(features) {
  const bounds = [Infinity, Infinity, -Infinity, -Infinity];
  for (const feature of features) for (const line of lines(feature)) for (const [x, y] of line) {
    bounds[0] = Math.min(bounds[0], x); bounds[1] = Math.min(bounds[1], y);
    bounds[2] = Math.max(bounds[2], x); bounds[3] = Math.max(bounds[3], y);
  }
  return features.length ? bounds : null;
}

function paint() {
  const canvas = byId("map"), context = canvas.getContext("2d");
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const pixelRatio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * pixelRatio); canvas.height = Math.round(height * pixelRatio);
  context.scale(pixelRatio, pixelRatio);
  context.font = "12px system-ui";
  context.fillStyle = "#496173";
  if (!state.extent || !state.features.length) {
    context.fillText("No documented lines match these filters.", 18, 28);
    state.active = null; byId("scale").textContent = "";
    return;
  }
  const [west, south, east, north] = state.extent;
  const correction = Math.cos((north + south) * Math.PI / 360);
  const scale = Math.min((width - 60) / (Math.max(east - west, .001) * correction),
                         (height - 56) / Math.max(north - south, .001));
  const mx = (west + east) / 2, my = (south + north) / 2;
  const project = ([lon, lat]) => [width / 2 + (lon - mx) * scale * correction, height / 2 - (lat - my) * scale];
  const inverse = (x, y) => [mx + (x - width / 2) / (scale * correction), my - (y - height / 2) / scale];
  state.active = {project, inverse};
  context.strokeStyle = "#dae8e9";
  for (let n = 1; n < 5; n++) {
    context.beginPath();
    context.moveTo(n * width / 5, 0); context.lineTo(n * width / 5, height);
    context.moveTo(0, n * height / 5); context.lineTo(width, n * height / 5);
    context.stroke();
  }
  context.fillText("N ↑", 15, 21);
  const hits = new Set(state.areas.map(feature => feature.id));
  const catalog = new Map(state.routes.map(route => [route.route_id, route.mode]));
  const selected = feature => feature.id === state.selectedLine || feature.properties.route_ids.includes(state.selected);
  for (const feature of [...state.features].sort((a, b) => Number(selected(a)) - Number(selected(b)))) {
    const categories = new Set(feature.properties.route_ids.map(id => catalog.get(id)));
    context.strokeStyle = selected(feature) ? "#102d43" : hits.has(feature.id) ? "#aa6215" :
      categories.size === 1 ? colors[[...categories][0]] || "#625786" : "#625786";
    context.lineWidth = selected(feature) || hits.has(feature.id) ? 4 : 2;
    context.lineJoin = "round";
    context.setLineDash(feature.properties.source === 'OSM' ? [] : [7, 3]);
    context.globalAlpha = selected(feature) || hits.has(feature.id) ? 1 : .66;
    for (const line of lines(feature)) {
      context.beginPath();
      line.forEach((point, index) => (index ? context.lineTo(...project(point)) : context.moveTo(...project(point))));
      context.stroke();
    }
  }
  context.globalAlpha = 1; context.setLineDash([]);
  byId("scale").textContent = "≈ " + (100 / scale * 111.2).toFixed(1) + " km";
  if (state.bounds) {
    const [w, s, e, n] = state.bounds, [x, y] = project([w, n]), [right, bottom] = project([e, s]);
    context.strokeStyle = "#aa6215";
    context.lineWidth = 1.5;
    context.setLineDash([5, 4]);
    context.strokeRect(x, y, right - x, bottom - y);
    context.setLineDash([]);
  }
}

function routeButtons(target, ids) {
  target.replaceChildren();
  const found = state.routes.filter(route => ids.includes(route.route_id));
  for (const route of found) button(target, route.route_name, () => openRoute(route.route_id));
}

function renderRoutes() {
  const list = byId("routes"), more = byId("more-routes");
  list.replaceChildren(); more.replaceChildren();
  byId("record-count").textContent = String(state.routes.length);
  if (!state.routes.length) node("li", "No route records match.", list);
  for (const route of state.routes.slice(0, state.routeCount)) {
    const item = node("li", undefined, list);
    const pick = button(item, route.route_name || route.route_id, () => openRoute(route.route_id));
    pick.setAttribute("aria-pressed", String(state.selected === route.route_id));
    pick.style.setProperty('--route-color', colors[route.mode] || '#625786');
    const linked = state.features.filter(f => f.properties.route_ids.includes(route.route_id));
    const status = route.source === 'OSM' ? 'OSM · Explicit member lines · service unverified' : linked.some(f => f.properties.candidate_route_ids.includes(route.route_id)) ? '△ Candidate match · unconfirmed' : linked.length ? '△ Source-linked line · unconfirmed' : '— No displayed map evidence';
    node('small', status, item).className = 'evidence';
    node("small", [modes[route.mode] || "Unknown mode", display(route.classification)].join(" · "), item);
  }
  if (state.routes.length > state.routeCount) button(more, "Show more records", () => {
    state.routeCount += 30; renderRoutes();
  });
}

async function refresh() {
  const request = ++state.generation;
  state.areaGeneration++;
  const filters = Object.fromEntries(new FormData(byId("filters")));
  delete filters.source; delete filters.geography;
  filters.q = filters.q.trim();
  const evidenceFilter = filters.evidence; delete filters.evidence;
  notify("Loading route records…");
  const [routes, features] = local ? await Promise.all([
    collect("routes", filters, "items"), collect("features", filters, "features"),
  ]) : [{records: demoRoutes.filter(route => includesRoute(route, filters))},
        {records: demoFeatures.filter(feature => demoRoutes.some(route =>
          feature.properties.route_ids.includes(route.route_id) && includesRoute(route, filters)))}];
  if (request !== state.generation) return;
  state.filters = filters; state.routes = routes.records; state.features = features.records;
  if (evidenceFilter) {
    state.routes = state.routes.filter(route => {
      const linked = state.features.filter(f => f.properties.route_ids.includes(route.route_id));
      return evidenceFilter === 'missing' ? !linked.length : evidenceFilter === 'candidate' ? linked.some(f => f.properties.candidate_route_ids.includes(route.route_id)) : linked.length;
    });
    const ids = new Set(state.routes.map(r => r.route_id));
    state.features = state.features.filter(f => f.properties.route_ids.some(id => ids.has(id)));
  }
  state.extent = overview(state.features); state.routeCount = 30;
  byId('chips').replaceChildren();
  for (const [key, value] of Object.entries({...filters, evidence: evidenceFilter})) if (value) {
    button(byId('chips'), key + ': ' + display(value) + ' ×', () => { byId('filters').elements[key].value = ''; return refresh(); });
  }
  state.selected = null;
  byId('route-detail').replaceChildren(node('p', 'Select a route to inspect its evidence.'));
  byId('workbench').hidden = true;
  state.selectedLine = null;
  renderRoutes(); paint();
  notify(state.routes.length ? "" : "No records match the selected filters.");
  if (state.bounds) await compareArea();
}

async function compareArea() {
  const request = ++state.areaGeneration;
  const bounds = boundsFrom(byId("area").elements.bbox.value);
  const result = local ? await collect("features", {...state.filters, bbox: bounds.join(",")}, "features") :
    {records: state.features.filter(item => demoIntersects(item, bounds))};
  if (request !== state.areaGeneration) return;
  state.bounds = bounds; state.areas = result.records.filter(f => state.features.some(current => current.id === f.id));
  byId("area-panel").open = true;
  const ids = [...new Set(state.areas.flatMap(feature => feature.properties.route_ids))];
  const counts = Object.entries(modes).map(([key, name]) => {
    const count = state.routes.filter(r => ids.includes(r.route_id) && r.mode === key).length;
    return name + " " + count;
  }).join(" · ");
  byId("area-results").textContent = state.areas.length
    ? state.areas.length + " documented lines intersecting this area · " + ids.length + " source-linked route records · " + counts
    : "No documented lines intersect the selected area under these filters.";
  routeButtons(byId("area-records"), ids);
  notify(""); paint();
}

async function openRoute(id) {
  const request = ++state.selection;
  const route = local ? await call("routes/" + encodeURIComponent(id)) : demoRoutes.find(item => item.route_id === id);
  if (request !== state.selection) return;
  state.selected = id; state.selectedLine = null; renderRoutes(); paint();
  const detail = byId("route-detail");
  detail.replaceChildren();
  node("h3", route.route_name, detail);
  document.body.dataset.view = 'inspect';
  byId('workbench').hidden = true;
  node('h3', 'Overview', detail);
  node('p', (modes[route.mode] || 'Unknown mode') + ' · ' + display(route.classification), detail);
  node('p', 'Source geography: ' + (route.localities?.map(x => x.locality_name || x.locality || x.name || x.label).filter(Boolean).join(', ') || 'Not supplied by this endpoint'), detail);
  node('h3', 'Direction evidence', detail);
  for (const direction of route.directions) node('p', 'Direction ' + direction.ordinal + ' · ' + display(direction.direction) + ' · ' + display(direction.association_status) + (direction.reason ? '. ' + direction.reason : ''), detail);
  node('h3', 'Map evidence', detail);
  const linked = state.features.filter(f => f.properties.route_ids.includes(id));
  node('p', linked.length ? linked.length + ' source-linked lines in this view. Structural checks do not establish direction identity or active service.' : 'No map geometry associated in the current view. This is unavailable evidence, not proof of a failed geometry check.', detail);
  for (const f of linked) node('p', (f.properties.candidate_route_ids.includes(id) ? '△ Candidate direction match — unconfirmed. ' : '△ Shared source file only — direction match unresolved. ') + 'Geometry: ' + display(f.properties.status), detail);
  node('h3', 'Review cases', detail);
  for (const item of route.cases) button(node('div', undefined, detail), 'Open case: ' + display(item.code), () => openCase(item.issue_id));
  if (!route.cases.length) node('p', 'No recorded cases for this route.', detail);
  const source = node('details', undefined, detail);
  node('summary', 'Source details', source);
  node('p', 'Source record: ' + route.source_record_id + ' · ' + display(route.source_status) + ' · ' + display(route.metadata_status), source);
  button(source, 'Copy record identifier', () => navigator.clipboard.writeText(route.source_record_id).then(() => notify('Identifier copied.')));
  notify("");
}

async function showQueue(offset = 0) {
  const cases = local ? await call("cases", {limit: state.caseCount, offset}) : {
    items: demoRoutes.map(route => ({...route.cases[0], route_name: route.route_name, ordinal: 1, project_review_count: storedReviews().filter(e=>e.issue_id===route.cases[0].issue_id).length})),
    total: demoRoutes.length,
  };
  const queue = byId("queue"), more = byId("more-cases");
  queue.replaceChildren(); more.replaceChildren();
  if (!cases.items.length) node("li", "No unresolved direction cases.", queue);
  for (const item of cases.items) {
    const row=node('li',undefined,queue);
    button(row,item.route_name + ' · direction ' + item.ordinal,()=>openCase(item.issue_id));
    node('small','△ Which line represents this direction?',row);
    node('small',item.project_review_count ? item.project_review_count + ' project reviews · source unresolved' : 'Not yet reviewed · source unresolved',row);
  }
  if (offset > 0) button(more, "Previous cases", () => showQueue(offset - state.caseCount));
  if (offset + state.caseCount < cases.total) button(more, "Next cases", () => showQueue(offset + state.caseCount));
}

function storedReviews() {
  return JSON.parse(localStorage.getItem(storageKey) || "[]");
}

async function openCase(id, scroll = true) {
  const request = ++state.caseSelection;
  let record;
  if (local) record = await call("cases/" + encodeURIComponent(id));
  else {
    const route = demoRoutes.find(item => item.cases.some(issue => issue.issue_id === id));
    record = {route, issue: route.cases[0], release_version: demoVersion,
      source_features: demoFeatures.filter(feature => feature.properties.route_ids.includes(route.route_id))
        .map(feature => ({feature_id: feature.id, status: "synthetic line", source_crs: "WGS84"})),
      history: storedReviews().filter(event => event.issue_id === id).reverse()};
  }
  if (request !== state.caseSelection) return;
  if (!state.routes.some(route => route.route_id === record.route.route_id)) {
    byId('filters').reset(); byId('filters').elements.q.value=record.route.route_id;
    await refresh();
    if (request !== state.caseSelection) return;
  }
  if (state.case?.issue.issue_id !== id) byId('review').elements.note.value = '';
  state.case = record;
  state.selected = record.route.route_id;
  state.selectedLine = null; paint(); renderRoutes();
  workspace('verification');
  document.body.dataset.view = 'inspect';
  byId('workbench').hidden = false;
  byId('route-detail').replaceChildren();
  const evidence = byId("case-evidence"), history = byId("history");
  evidence.replaceChildren(); history.replaceChildren();
  node("h3", record.route.route_name, evidence);
  node("p", display(record.issue.code) + " · " + record.issue.detail, evidence);
  const sourceDetails = node('details', undefined, evidence);
  node('summary', 'Source identifiers and release', sourceDetails);
  node('p', 'Case ' + record.issue.issue_id + ' · release ' + record.release_version, sourceDetails);
  node("p", "Source record " + record.route.source_record_id + " · Source status " + display(record.route.source_status), sourceDetails);
  for (const direction of record.route.directions) {
    node("p", "Direction " + direction.ordinal + " · " + display(direction.direction) + " · " +
      display(direction.association_status) + (direction.reason ? " · " + direction.reason : ""), evidence);
  }
  if (!record.source_features.length) node("p", "No geometry evidence was recorded for this source file.", evidence);
  for (const feature of record.source_features) node("p",
    "Source geometry · " + display(feature.status) + " · " + display(feature.source_crs) +
    (feature.geodesic_km == null ? "" : " · " + feature.geodesic_km + " km") +
    (feature.reason ? " · " + feature.reason : ""), evidence);
  if (!record.history.length) node("li", "No decisions saved for this case.", history);
  for (const event of record.history) node("li",
    decisions[event.decision] + " · " + event.reviewer + " · " + event.created_at + " · " + event.note, history);
  byId("review").hidden = false;
  if (scroll) evidence.scrollIntoView({block: "nearest"});
}

async function saveReview(form) {
  const data = Object.fromEntries(new FormData(form));
  data.reviewer = data.reviewer.trim(); data.note = data.note.trim();
  if (!data.reviewer || !data.note || !Object.hasOwn(decisions, data.decision)) throw new Error("Enter a reviewer and evidence note.");
  const issueId = state.case.issue.issue_id, release = state.case.release_version;
  const action = form.querySelector("button");
  action.disabled = true; action.textContent = "Saving project review…"; notify("Saving project review…");
  try {
    if (local) await call("cases/" + encodeURIComponent(issueId) + "/reviews", {}, {...data, release_version: release});
    else localStorage.setItem(storageKey, JSON.stringify([...storedReviews(), {...data, release_version: release,
      issue_id: issueId, created_at: new Date().toISOString()}]));
    if (state.case.issue.issue_id === issueId) {
      form.elements.note.value = "";
      await openCase(issueId, false);
      await showQueue();
    }
    notify(local ? "Project decision saved to local SQLite history." : "Demo decision saved in this browser.");
  } finally { action.disabled = false; action.textContent = "Save project review"; }
}

function formAction(id, action) {
  byId(id).addEventListener("submit", event => {
    event.preventDefault();
    Promise.resolve().then(() => action(event.target)).catch(showError);
  });
}

function wireMap() {
  const canvas = byId("map");
  let start;
  canvas.addEventListener("pointerdown", event => {
    if (!state.active || event.button !== 0) return;
    start = [event.offsetX, event.offsetY]; canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointercancel", () => { start = null; });
  canvas.addEventListener("pointerup", event => {
    if (!start || !state.active) return;
    const point = [event.offsetX, event.offsetY], first = start;
    start = null;
    if (Math.hypot(point[0]-first[0],point[1]-first[1]) > 8 && state.tool === 'pan') {
      const a=state.active.inverse(...first), b=state.active.inverse(...point);
      state.extent=state.extent.map((v,i)=>v+a[i%2]-b[i%2]); paint(); return;
    }
    if (state.tool === 'area') {
      if (Math.abs(point[0]-first[0]) < 8 || Math.abs(point[1]-first[1]) < 8) { notify('Draw a wider rectangle to select an area.', true); return; }
      const a = state.active.inverse(...first), b = state.active.inverse(...point);
      byId("area").elements.bbox.value = [Math.min(a[0], b[0]), Math.min(a[1], b[1]),
        Math.max(a[0], b[0]), Math.max(a[1], b[1])].map(n => n.toFixed(5)).join(", ");
      compareArea().catch(showError);
      return;
    }
    let chosen, nearest = 9;
    for (const feature of state.features) for (const line of lines(feature)) for (let i = 1; i < line.length; i++) {
      const [x, y] = state.active.project(line[i - 1]), [xx, yy] = state.active.project(line[i]);
      const dx = xx - x, dy = yy - y;
      const w = Math.max(0, Math.min(1, ((point[0] - x) * dx + (point[1] - y) * dy) / (dx * dx + dy * dy || 1)));
      const distance = Math.hypot(point[0] - x - w * dx, point[1] - y - w * dy);
      if (distance < nearest) { chosen = feature; nearest = distance; }
    }
    if (!chosen) return;
    openRoute(chosen.properties.route_ids[0]).then(() => {
      state.selectedLine = chosen.id; paint();
      byId("area-results").textContent = "Selected line · " + display(chosen.properties.status) +
        " · " + chosen.properties.candidate_route_ids.length + " candidate route matches";
      routeButtons(byId("area-records"), chosen.properties.route_ids);
    }).catch(showError);
  });
  canvas.addEventListener('wheel', event => { event.preventDefault(); zoom(event.deltaY > 0 ? 1.15 : .87); }, {passive:false});
  canvas.addEventListener('keydown', event => {
    if (['+','=','-'].includes(event.key)) {event.preventDefault();zoom(event.key==='-'?1.3:.75);}
    if (event.key.startsWith('Arrow') && state.extent) { event.preventDefault(); const [w,s,e,n]=state.extent; const dx=(e-w)*.15*(event.key==='ArrowRight'?1:event.key==='ArrowLeft'?-1:0); const dy=(n-s)*.15*(event.key==='ArrowUp'?1:event.key==='ArrowDown'?-1:0); state.extent=[w+dx,s+dy,e+dx,n+dy]; paint(); }
  });
  canvas.addEventListener('pointermove', event => {
    if (start || !state.active) return;
    let found;
    for (const feature of state.features) for (const line of lines(feature)) for(let i=1;i<line.length;i++) {
      const [x,y]=state.active.project(line[i-1]),[xx,yy]=state.active.project(line[i]),dx=xx-x,dy=yy-y;
      const t=Math.max(0,Math.min(1,((event.offsetX-x)*dx+(event.offsetY-y)*dy)/(dx*dx+dy*dy||1)));
      if(Math.hypot(event.offsetX-x-t*dx,event.offsetY-y-t*dy)<7) found=feature;
    }
    byId('tooltip').hidden=!found;
    if(found) byId('tooltip').textContent=(state.routes.find(r=>found.properties.route_ids.includes(r.route_id))?.route_name || 'Documented line') + (found.properties.source === 'OSM' ? ' · OSM membership' : ' · Candidate association');
  });
  canvas.addEventListener('pointerleave',()=>byId('tooltip').hidden=true);
  new ResizeObserver(paint).observe(canvas);
}

function workspace(name) {
  document.body.dataset.workspace = name;
  byId('route-list').hidden = name !== 'network';
  byId('case-list').hidden = name !== 'verification';
  byId('filters').hidden = name !== 'network';
  byId('network-tab').setAttribute('aria-pressed', name === 'network');
  byId('verification-tab').setAttribute('aria-pressed', name === 'verification');
  if (name === 'network') byId('workbench').hidden = true;
}
function zoom(factor) {
  if (!state.extent) return;
  const [w,s,e,n] = state.extent, x=(w+e)/2,y=(s+n)/2;
  const dx=Math.min(180, Math.max(.00001,(e-w)*factor/2)),dy=Math.min(90,Math.max(.00001,(n-s)*factor/2));
  state.extent=[x-dx,y-dy,x+dx,y+dy]; paint();
}
async function initialize() {
  state.tool = 'pan';
  for (const view of document.querySelectorAll('[data-view]')) if (view.tagName === 'BUTTON') view.onclick = () => { document.body.dataset.view = view.dataset.view; paint(); };
  for (const name of ['browse','inspect']) byId('toggle-'+name).onclick = event => { document.body.classList.toggle('hide-'+name); event.target.setAttribute('aria-expanded', !document.body.classList.contains('hide-'+name)); };
  byId('network-tab').onclick = () => { workspace('network'); document.body.dataset.view='browse'; };
  byId('verification-tab').onclick = () => { workspace('verification'); document.body.dataset.view='browse'; };
  byId('clear-filters').onclick = () => { byId('filters').reset(); refresh().catch(showError); };
  byId('zoom-in').onclick = () => zoom(.7);
  byId('zoom-out').onclick = () => zoom(1.4);
  byId('fit-network').onclick = () => { state.extent=overview(state.features); paint(); };
  byId('fit-selection').onclick = () => { const selected=state.features.filter(f => f.properties.route_ids.includes(state.selected)); if (!selected.length) return notify('The selected record has no displayed map geometry.'); state.extent=overview(selected); paint(); };
  for (const tool of ['pan','area']) byId(tool+'-tool').onclick = () => { state.tool=tool; for (const name of ['pan','area']) byId(name+'-tool').setAttribute('aria-pressed',name===tool); byId('map').style.cursor=tool==='area'?'crosshair':'grab'; notify(tool==='area'?'Drag a rectangle to compare documented lines.':'Drag to pan or select a line.'); };

  byId("data-scope").textContent = local ? "Private local workspace" :
    "Public demo · Synthetic data";
  byId("storage-scope").textContent = local ? "Decisions are stored on this computer in the private SQLite history. Reviewer names are self-declared." :
    "Demo decisions stay in this browser’s local storage. Clearing site data erases them.";
  if (local) {
    const health = await call("health");
    byId("release").textContent = "Verified release " + health.release_version;
    const stats = health.statistics;
    byId("release-stats").textContent = "Integrity verified · " + stats.normalized_route_records + " records · " +
      stats.feature_statuses.geometry_pass + " passing features · " + stats.association_statuses.unresolved + " unresolved directions";
  } else byId("release").textContent = "Synthetic demonstration";
  formAction("filters", refresh);
  formAction("area", compareArea);
  formAction("review", saveReview);
  byId("clear-area").addEventListener("click", () => {
    state.areaGeneration++; state.bounds = null; state.areas = []; state.selectedLine = null;
    byId("area").reset(); byId("area-records").replaceChildren();
    byId("area-results").textContent = "Select an area to compare intersections with documented lines.";
    paint();
  });
  wireMap();
  await Promise.all([refresh(), showQueue()]);
}

window.addEventListener("DOMContentLoaded", () => initialize().catch(showError));
