/* Source-aware static release adapter. The private API and review store remain separate. */
'use strict';
let releaseBundle, releaseBase, releaseManifest, originalFeatures;
const originalInitialize=initialize, privateRefresh=refresh, privateRoute=openRoute, privateQueue=showQueue;
const hex = buffer => Array.from(new Uint8Array(buffer),b=>b.toString(16).padStart(2,'0')).join('');
async function checkedFile(name) {
  const response=await fetch(releaseBase+'/'+name);
  if(!response.ok)throw Error('Release file unavailable: '+name);
  const bytes=await response.arrayBuffer();
  const hash=hex(await crypto.subtle.digest('SHA-256',bytes));
  if(hash!==releaseManifest.outputs[name])throw Error('Release integrity failed. Reload after restoring the checked release.');
  return JSON.parse(new TextDecoder().decode(bytes));
}
function configureSelect(name, values, title) {
  const select=byId('filters').elements[name];select.replaceChildren(new Option(title,''));
  for(const value of [...new Set(values)].filter(Boolean).sort())select.add(new Option(display(value),value));
}
initialize=async function() {
  if(local){byId('source-filter').hidden=true;byId('geography-filter').hidden=true;return originalInitialize();}
  notify('Checking OSM release and loading documented geometry…');
  const p=await fetch('./data/latest.json');if(!p.ok)throw Error('Public data release unavailable. Build the static OSM layer before serving.');
  const pointer=await p.json();
  if(!/^[a-f0-9]{20}$/.test(pointer.version)||pointer.release!=='releases/'+pointer.version)throw Error('Invalid release pointer');
  releaseBase='./data/'+pointer.release;
  const response=await fetch(releaseBase+'/manifest.json');if(!response.ok)throw Error('Release manifest unavailable');
  releaseManifest=await response.json();
  if(releaseManifest.version!==pointer.version || Object.keys(releaseManifest.outputs).sort().join(',')!=='bundle.json,originals.geojson,provenance.json')throw Error('Invalid release manifest');
  const identity=hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(releaseManifest.outputs)))).slice(0,20);
  if(identity!==pointer.version)throw Error('Manifest identity mismatch');
  releaseBundle=await checkedFile('bundle.json');
  if(!['osm_public','maintainer_authorized_ltfrb'].includes(releaseBundle.publication) && !['127.0.0.1','localhost'].includes(location.hostname))throw Error('This LTFRB proposal is not authorized for public hosting.');
  if(releaseBundle.publication==='osm_public' && releaseBundle.routes.some(r=>r.source!=='OSM'))throw Error('Public source boundary violation');
  demoRoutes.splice(0,demoRoutes.length,...releaseBundle.routes);
  demoFeatures.splice(0,demoFeatures.length,...releaseBundle.features);
  for(const r of demoRoutes){modes[r.mode]=display(r.mode);colors[r.mode]=r.source==='OSM'?'#08736f':({PUJ:'#a86a14',PUB:'#22559f',UV_EXPRESS:'#9e4d19'}[r.mode]||'#22559f');}
  configureSelect('source',demoRoutes.map(r=>r.source),'All sources');
  configureSelect('mode',demoRoutes.map(r=>r.mode),'All source modes');
  configureSelect('classification',demoRoutes.map(r=>r.classification),'All source classifications');
  configureSelect('geography',demoRoutes.flatMap(r=>r.geography),'All source geographic labels');
  byId('filters').elements.source.onchange=()=>{
    const source=byId('filters').elements.source.value, rows=demoRoutes.filter(r=>!source||r.source===source);
    configureSelect('mode',rows.map(r=>r.mode),'All source modes');configureSelect('classification',rows.map(r=>r.classification),'All source classifications');configureSelect('geography',rows.flatMap(r=>r.geography),'All source geographic labels');
  };
  await originalInitialize();
  byId('data-scope').textContent=releaseBundle.publication==='osm_public'?'OSM · Historical public data':releaseBundle.publication==='maintainer_authorized_ltfrb'?'OSM + LTFRB · Documented evidence':'LOCAL PREVIEW · OSM + proposed LTFRB';
  byId('release').textContent='Checked static release '+pointer.version;
  byId('release-stats').textContent='OSM snapshot: 1 August 2026. Complete relations can extend outside Davao; the initial viewport is not a city boundary. Display simplified at 10 m; comparisons use original lines.';
  byId('verification-tab').textContent='Verification guide';
  button(document.querySelector('.map-tools'),'Davao view',()=>{state.extent=[125.45,6.95,125.75,7.30];paint();notify('Davao-area viewport; not an administrative boundary. Fit network shows complete intercity relations.');});
  document.querySelector('.legend').textContent='Teal: OSM membership · Blue / amber: LTFRB candidates · Thick: selected · Dashed: candidate association';
  const attribution=byId('attribution');attribution.hidden=false;
  const download=node('a','Download exported line geometry (unsimplified GeoJSON)',byId('release-panel'));download.href=releaseBase+'/originals.geojson';download.download='';
  const provenance=node('a','Download provenance and licence',byId('release-panel'));provenance.href=releaseBase+'/provenance.json';
  const records=node('a','Download selected fields and display data',byId('release-panel'));records.href=releaseBase+'/bundle.json';
  byId('storage-scope').textContent='Public exploration does not write private reviews. Use the local workbench for append-only project decisions.';
};
refresh=async function() {
  if(local){const source=byId('filters').elements.source,geo=byId('filters').elements.geography;source.disabled=true;geo.disabled=true;return privateRefresh();}
  const filters=Object.fromEntries(new FormData(byId('filters')));filters.q=filters.q.trim().toLowerCase();
  state.filters=filters;
  state.routes=demoRoutes.filter(r=>(!filters.source||r.source===filters.source)&&(!filters.q||(r.route_name+' '+r.route_id).toLowerCase().includes(filters.q))&&(!filters.mode||r.mode===filters.mode)&&(!filters.classification||r.classification===filters.classification)&&(!filters.geography||r.geography.includes(filters.geography)));
  state.routes=state.routes.filter(r=>{const fs=demoFeatures.filter(f=>f.properties.route_ids.includes(r.route_id));return !filters.evidence||filters.evidence==='linked'&&fs.length||filters.evidence==='missing'&&!fs.length||filters.evidence==='candidate'&&fs.some(f=>f.properties.candidate_route_ids.includes(r.route_id));});
  const ids=new Set(state.routes.map(r=>r.route_id));state.features=demoFeatures.filter(f=>f.properties.route_ids.some(id=>ids.has(id)));
  if(!ids.has(state.selected)){state.selected=null;byId('route-detail').replaceChildren(node('p','Select a documented record to inspect its source evidence.'));}
  state.extent=state.routes.length===demoRoutes.length?[125.45,6.95,125.75,7.30]:overview(state.features);state.routeCount=30;state.selectedLine=null;state.generation++;
  byId('chips').replaceChildren();for(const [key,value]of Object.entries(filters))if(value)button(byId('chips'),key+': '+value+' ×',()=>{byId('filters').elements[key].value='';return refresh();});
  renderRoutes();paint();notify(state.routes.length?'':'No route records match these source filters.');
  if(state.bounds)await compareArea();
};
const privateArea=compareArea;
compareArea=async function(){
  if(local)return privateArea();
  const request=++state.areaGeneration;const bounds=boundsFrom(byId('area').elements.bbox.value);
  notify('Comparing original documented lines…');
  originalFeatures ??= (await checkedFile('originals.geojson')).features;
  if(request!==state.areaGeneration)return;
  const visible=new Set(state.features.map(f=>f.id));state.areas=originalFeatures.filter(f=>visible.has(f.id)&&demoIntersects(f,bounds));state.bounds=bounds;
  byId('area-panel').open=true;
  byId('area-results').textContent=state.areas.length+' documented lines intersecting this area. Counts are grouped OSM relations or LTFRB candidate directions, not services or transfers.';
  routeButtons(byId('area-records'),[...new Set(state.areas.flatMap(f=>f.properties.route_ids))]);paint();notify('Area comparison used unsimplified geometry.');
};
openRoute=async function(id){
  if(local)return privateRoute(id);
  const r=demoRoutes.find(r=>r.route_id===id);if(!r)throw Error('Record unavailable');
  state.selected=id;state.selectedLine=null;renderRoutes();paint();document.body.dataset.view='inspect';byId('workbench').hidden=true;
  const detail=byId('route-detail');detail.replaceChildren();node('h3',r.route_name,detail);node('p',r.source+' · '+r.observed_at,detail).className='badge';
  node('h3','Overview',detail);node('p',display(r.mode)+' · '+r.classification,detail);node('p','Source geography: '+(r.geography.join(', ')||'Not supplied'),detail);
  node('h3','Direction evidence',detail);for(const d of r.directions)node('p',(r.source==='OSM'?'Endpoint tags: ':'Direction '+d.ordinal+': ')+(d.direction||'Not supplied').replace('Not supplied to Not supplied','Not supplied')+' · '+display(d.association_status)+(d.declared_km==null?'':' · Source-declared '+d.declared_km+' km'),detail);
  node('h3','Map evidence',detail);const fs=demoFeatures.filter(f=>f.properties.route_ids.includes(id));
  node('p',fs.length?(r.source==='OSM'?'Explicit OSM relation membership.':'Candidate LTFRB direction matches only; not confirmed.'):'No associated map geometry in this projection. Unresolved evidence is retained as a record.',detail);
  node('h3','Quality and limitations',detail);node('p',r.quality,detail);node('p','Structural checks do not establish active service, boarding access or transfers. No cross-source identity matching was performed.',detail);
  node('h3','Review cases',detail);node('p','Private LTFRB cases and reviewer history are available only in the local verification workbench. Public exploration records no review decision.',detail);
  const provenance=node('details',undefined,detail);node('summary','Provenance',provenance);node('p',r.provenance,provenance);node('p','Display geometry uses 10 m simplification. Download original lines from Data release.',provenance);
  notify('Selected '+r.source+' record.');
};
showQueue=async function(offset=0){if(local)return privateQueue(offset);byId('queue').replaceChildren(node('li','Open the private local workspace to review real LTFRB cases and append decisions. This static explorer cannot access that store.'));byId('more-cases').replaceChildren();};
