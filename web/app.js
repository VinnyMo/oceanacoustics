"use strict";
const repository = "https://github.com/VinnyMo/oceanacoustics";
const sourceRegistry = "https://registry.opendata.aws/pacific-sound/";
const byId = id => document.getElementById(id);
const pages = {
  observatory: ["Pacific Sound / MBARI", "Observatory", "Explore the deep-ocean soundscape off Monterey Bay, California."],
  discoveries: ["Acoustic evidence", "Discoveries", "Listen to preserved candidates and compare their acoustic signatures."],
  statistics: ["Processing ledger", "Statistics", "Measurements from the most recently published processing snapshot."],
  research: ["Field notes", "Research", "Questions, methods and evidence from the open observatory."],
  contribute: ["Open science", "Contribute", "Reproduce an observation or help develop the analysis."]
};
const num = (x, digits=1) => typeof x === "number" && Number.isFinite(x)
  ? x.toLocaleString("en-US", {maximumFractionDigits: digits}) : "Unknown";
function when(value) {
  if (!value) return "Unknown";
  const t = new Date(value);
  return Number.isNaN(t.getTime()) ? "Unknown" : t.toISOString().slice(0,19).replace("T"," ")+" UTC";
}
function elapsed(n) {
  if (typeof n !== "number" || n < 0) return "Unknown";
  if (n < 60) return num(n,1)+" s";
  if (n < 3600) return num(n/60)+" min";
  if (n < 86400) return num(n/3600)+" h";
  return num(n/86400)+" days";
}
function bytes(n) {
  return typeof n === "number" ? (n < 1e9 ? num(n/1e6,2)+" MB" : num(n/1e9,2)+" GB") : "Unknown";
}
function el(tag, cls, value) {
  const node = document.createElement(tag);
  if (cls) node.className=cls;
  if (value != null) node.textContent=String(value);
  return node;
}
function link(text, url) {
  const a = el("a", "", text);
  a.href = url;
  return a;
}
function media(value) {
  if (typeof value !== "string" || !value) return null;
  try {
    const u = new URL(value,location.origin+"/");
    return u.origin === location.origin && /^https?:$/.test(u.protocol) ? u.href : null;
  } catch { return null; }
}
function picture(url, alt, caption) {
  const figure=el("figure","figure");
  if (media(url)) {
    const img=el("img","visual");
    img.src=media(url); img.alt=alt; img.loading="lazy"; figure.append(img);
    if (caption) figure.append(el("figcaption","figure-note",caption));
  } else figure.append(el("p","muted",alt+" unavailable."));
  return figure;
}
function spectrogram(e,caption) {
  const plot=picture(e.spectrogram_url,"Relative spectral intensity of the recorded audio",caption);
  const img=plot.querySelector("img");
  if (!img) return plot;
  const axis=el("div","plot-area"), freq=el("div","freq-axis");
  for (const tick of (e.sample_rate_hz===16000?["8 kHz","4 kHz","0 Hz"]:["1 kHz","500 Hz","0 Hz"])) freq.append(el("span","",tick));
  const time=el("div","time-axis");
  for(const ratio of [0,.25,.5,.75,1]) time.append(el("span","",num(e.duration_seconds*ratio)+" s"));
  plot.prepend(axis);axis.append(freq,img,time);return plot;
}
function player(e) {
  const url=media(e.audio_url);
  if (!url) return el("p","muted","Playback unavailable.");
  const audio=el("audio");
  audio.controls=true; audio.preload="none"; audio.src=url;
  audio.setAttribute("aria-label","Original-speed recording "+e.id);
  return audio;
}
function facts(items,cls="facts") {
  const dl=el("dl",cls);
  for (const [term,desc] of items) {
    const row=el("div"); row.append(el("dt","",term), el("dd","",desc??"Unknown")); dl.append(row);
  }
  return dl;
}
const events=()=>Array.isArray(state?.events) ? state.events : [];
const nameOf=e=>String(e.classification || "Unreviewed candidate").replaceAll("_"," ");
const detailLink=e=>"#discovery/"+encodeURIComponent(e.id);
function card(e,options={}) {
  const c=el("article","card"), heading=el("h3");
  c.append(el("p","label",nameOf(e)));
  heading.append(link(typeof e.frequency_hz==="number"?num(e.frequency_hz)+" Hz candidate":"Acoustic candidate",detailLink(e)));
  c.append(heading,el("p","small muted",when(e.recorded_at)));
  c.append(picture(e.spectrogram_url,"Spectrogram of acoustic candidate",""),player(e));
  c.append(el("p","small muted",elapsed(e.duration_seconds)+" · "+(e.location || "MBARI, Monterey Bay")));
  c.append(link("Inspect recording →",detailLink(e)));
  if(options.onCompare){
    const label=el("label","compare-check"), checkbox=el("input");
    checkbox.type="checkbox";checkbox.checked=comparison.has(String(e.id));
    checkbox.onchange=()=>options.onCompare(e,checkbox.checked);label.append(checkbox," Compare recording");c.append(label);
  }
  return c;
}
function cards(entries, node,options) {
  const list=el("div","catalog");
  if (!entries.length) {node.append(el("p","empty","No matching candidates in the published catalog."));return;}
  for (const e of entries) list.append(card(e,options));
  node.append(list);
}
function observatory(view) {
  const latest=state.latest, stats=state.stats || {};
  if (!latest) {view.append(el("p","empty","Waiting for the first processed recording."));return;}
  const grid=el("div","observ-grid"), plot=el("section","panel pad"), head=el("div","panel-head");
  const mode = /backfill|histor/i.test(latest.mode) ? "Historical backfill" : "Delayed archive";
  head.append(el("h2","","Latest spectrogram"),el("span","pill",mode));
  plot.append(head,spectrogram(latest,"Relative spectral intensity · Colors scaled within this interval"));
  if(latest.zero_fraction===1)plot.append(el("p","figure-note","All samples in this interval are zero. This interval cannot establish acoustic absence."));
  plot.append(facts([["Recording time",when(latest.recorded_at)],["Processed",when(latest.processed_at)],["Analyzed interval",elapsed(latest.duration_seconds)]],"measurements"));
  const site=el("section","panel pad");
  site.append(el("p","label","Hydrophone"),el("h2","",latest.location||"Monterey Bay"),facts([
    ["Archive","MBARI Pacific Sound · "+((latest.sample_rate_hz||2000)/1000)+" kHz"],["Archive modification time",when(latest.archive_modified_at)],
    ["Publication delay",elapsed(latest.publication_delay_seconds)],
    ...(latest.first_seen_lag_seconds!=null?[["Recording to project’s first observation",elapsed(latest.first_seen_lag_seconds)]]:[]),["Last reported processing status",state.status||"Unknown"],
    ["Historical coverage",num(stats.backfill_hours,3)+" h"]
  ]));grid.append(plot,site);view.append(grid);
  const title=el("div","section-head");title.append(el("h2","","Recent acoustic detections"),link("Browse catalog →","#discoveries"));view.append(title);cards(events().slice(0,3),view);
}
let filter="", group="";
const comparison=new Set();
async function discoveries(view) {
  const totalPages=Math.max(1,Math.ceil(state.stats.events/100));
  const current=Math.min(totalPages,Math.max(1,parseInt(route().id||"1",10)||1));
  let all=events();
  if(current>1){
    const wait=el("p","muted","Loading catalog page…");view.append(wait);
    try{
      const reply=await fetch("/data/catalog/"+current+".json",{cache:"no-store"});
      if(!reply.ok)throw Error();
      all=await reply.json();if(!Array.isArray(all))throw Error();
    }catch{wait.textContent="This catalog page could not be loaded.";view.append(link("Return to first page","#discoveries"));return;}
    if(!view.isConnected)return;
    wait.remove();
  }
  const controls=el("div","catalog-tools"), result=el("div");
  const term=el("label","","Classification "), select=el("select");
  for(const opt of ["",...new Set(all.map(nameOf))]) {const o=el("option","",opt||"All classifications");o.value=opt;select.append(o);}
  select.value=filter;
  term.append(select); controls.append(term);
  if(group){const clear=el("button","","Clear group filter");clear.onclick=()=>{group="";render()};controls.append(el("span","","Group "+group),clear);}
  const compare=el("button"); const syncCompare=()=>{compare.textContent="Compare selected ("+comparison.size+")";compare.disabled=comparison.size<2;};
  const onCompare=(e,checked)=>{const id=String(e.id);if(checked&&comparison.size>=6){controls.querySelector(".selection-limit")?.remove();controls.append(el("span","selection-limit","Select up to six recordings."));apply();return;}if(checked)comparison.add(id);else comparison.delete(id);syncCompare();};
  compare.onclick=()=>{location.hash="compare/"+Array.from(comparison).map(encodeURIComponent).join(",");};
  controls.append(compare);syncCompare();
  const apply=()=>{filter=select.value;result.replaceChildren();const subset=all.filter(e=>(!filter||nameOf(e)===filter)&&(!group||String(e.group_id)===group));result.append(el("p","small muted",subset.length+" of "+all.length+" entries on this page"));cards(subset,result,{onCompare});};
  select.onchange=apply;view.append(controls,result);apply();
  if(totalPages>1){
    const pager=el("div","catalog-tools");pager.setAttribute("aria-label","Catalog pagination");
    if(current>1)pager.append(link("← Newer recordings","#discoveries/"+(current-1)));
    pager.append(el("span","muted","Page "+current+" of "+totalPages));
    if(current<totalPages)pager.append(link("Older recordings →","#discoveries/"+(current+1)));
    view.append(pager);
  }
}
async function findEvent(id) {
  let e=events().find(x=>String(x.id)===id);
  if (!e && /^[A-Za-z0-9_-]{1,160}$/.test(id)) {
    try {const r=await fetch("/data/events/"+encodeURIComponent(id)+".json");if(r.ok){const found=await r.json();if(String(found.id)===id)e=found;}} catch {}
  }
  return e;
}
async function detail(id,view) {
  const e=await findEvent(id);
  if (route().id!==id || !view.isConnected) return;
  if (!e) {view.append(el("p","empty","This recording could not be found."),link("Browse discoveries","#discoveries"));return;}
  const box=el("article","panel pad detail");
  box.append(el("p","label",nameOf(e)),el("h2","",typeof e.frequency_hz==="number"?num(e.frequency_hz)+" Hz candidate":"Acoustic candidate"),
    el("p","sourceid",e.id),player(e),el("p","figure-note","Original speed · Browser playback copy"));
  box.append(spectrogram(e,"Relative spectral intensity · Colors scaled within this clip"),picture(e.waveform_url,"Candidate waveform","Amplitude through time"));
  box.append(facts([["Recorded",when(e.recorded_at)],["Location",e.location||"MBARI, Monterey Bay"],["Clip duration",elapsed(e.duration_seconds)],["Peak frequency",num(e.frequency_hz)+" Hz"],["Source identifier",e.source_id],["Detector",e.algorithm],["Score above background",num(e.score_db,2)+" dB"],["Review status",e.review_status||"Unreviewed"]],"measurements"));
  if(e.reference_comparison?.scores){
    const scores=e.reference_comparison.scores;
    box.append(el("h3","","Coastal reference comparison"),facts([["UF310 correlation",num(scores.UF310,3)],["UF440 correlation",num(scores.UF440,3)]]),
      el("p","small muted","Correlation compares spectral shape with two coastal development excerpts. A score alone cannot identify the sound source."));
  }
  const links=el("p","links");
  for(const [label,url] of [["Download playback audio",e.audio_url],["Download lossless excerpt",e.lossless_url]]) {
    if(media(url)){const a=link(label,media(url));a.download="";links.append(a);}
  }
  if (e.source_url) {try {const u=new URL(e.source_url);if(u.protocol==="https:")links.append(link("Archive recording",u.href));}catch{}}
  links.append(link("Permanent link",detailLink(e)));const attribution=el("p","small muted");
  attribution.append("Recording by Monterey Bay Aquarium Research Institute, ",link("Pacific Sound",sourceRegistry),". Original-speed excerpt and encoded playback copy under ",link("CC BY 4.0","https://creativecommons.org/licenses/by/4.0/"),".");
  box.append(links,attribution);
  view.append(box);
  const related=e.group_id!=null?events().filter(other=>other.id!==e.id&&other.group_id===e.group_id):[];
  if (related.length) {const head=el("div","section-head");const a=link("Browse group →","#discoveries");a.onclick=()=>{group=String(e.group_id);filter=""};head.append(el("h2","","Compare recordings in this group"),a);view.append(head);cards(related.slice(0,6),view);}
}
function statistics(view) {
  const s=state.stats||{}, grid=el("div","stats");
  for (const [label,value] of [["Analyzed audio",num(s.hours_analyzed,3)+" h"],["Distinct recording time",elapsed(s.coverage_seconds)],["Source data processed",bytes(s.bytes_processed)],["Historical coverage",num(s.backfill_hours,3)+" h"],["Processing speed",num(s.processing_speed,2)+"× real time"],["Detected events",num(s.events,0)],["Recurring unidentified groups",num(s.recurring_groups,0)],["Human-reviewed events",num(s.reviewed,0)],["Inventoried source files",num(s.inventoried_files,0)],["All-zero intervals",num(s.silent_windows,0)],["Storage used",bytes(s.storage_bytes)],["Worker heartbeat streak",elapsed(s.uptime_seconds)],["Last successful acquisition",when(s.last_acquisition)]]) {
    const item=el("div","panel metric");item.append(el("small","",label),el("strong","",value));grid.append(item);
  }
  view.append(grid,el("p","muted small","Archive coverage is reported in analyzed hours. The total duration of available archive recordings has yet to be inventoried."),el("p","small muted","Snapshot generated "+when(state.generated_at)));
  if(events().length){view.append(el("h2","","Classification in the most recent 100 candidates"));const counts=new Map();events().forEach(e=>counts.set(nameOf(e),(counts.get(nameOf(e))||0)+1));view.append(facts([...counts]));}
}
function prose(view,sections) {
  const body=el("div","prose");
  for(const [title,paragraph,links] of sections){const section=el("section","panel pad");section.append(el("h2","",title),el("p","",paragraph));const items=el("div","links");for(const [label,url] of links||[])items.append(link(label,url));section.append(items);body.append(section);}
  view.append(body);
}
function research(view) {prose(view,[
  ["What recurs in the deep ocean?","We measure changes in underwater sound and preserve excerpts for review. Our first question is whether similar narrowband events recur across independent recording dates at the Monterey Accelerated Research System hydrophone.",[["Study protocol",repository+"/blob/main/RESEARCH.md"]]],
  ["From recording to candidate","The baseline measures spectral energy against local background. Each candidate links its analysis to an archive identifier and recording time. Human review is needed to attribute a source. A quiet analyzed interval contributes to coverage even when it yields no candidates.",[["Experiment results","#statistics"],["Inspect candidates","#discoveries"]]],
  ["Coastal fish choruses","UF310 and UF440 are reference targets from California sanctuary studies. Their coastal recordings and Monterey Bay’s deep offshore observations differ in habitat, propagation and instrumentation. Frequency alone cannot identify a chorus.",[["Kim et al., ICES Journal of Marine Science","https://doi.org/10.1093/icesjms/fsag096"],["Dryad annotations","https://doi.org/10.5061/dryad.q2bvq83sw"]]],
  ["Limits of the observations","The 16 kHz source covers frequencies below 8 kHz. Earlier 2 kHz excerpts cover frequencies below 1 kHz. Weather, vessels, instruments and biological sources can produce overlapping signatures. Audited examples and independent held-out recordings are needed to estimate sensitivity and false alarms.",[["MBARI archive",sourceRegistry],["Pacific Sound documentation","https://docs.mbari.org/pacific-sound/"]]]
]);}
function contribute(view){prose(view,[
  ["Reproduce a recording","Start with a candidate’s permanent link, note its source identifier and UTC timestamp, then follow the repository setup and processing instructions.",[["Start here",repository+"/blob/main/START_HERE.md"],["Source code",repository]]],
  ["Contribute analysis","Propose a reproducible experiment, document review criteria or improve the detector. Include the algorithm version, source identifiers and measured results with your contribution.",[["Contribution guidelines",repository+"/blob/main/CONTRIBUTING.md"],["Research protocol",repository+"/blob/main/RESEARCH.md"]]],
  ["Future collaboration","Distributed processing and AI-assisted review are roadmap items. The public observatory currently publishes read-only results.",[["Roadmap",repository+"/blob/main/ROADMAP.md"]]]
]);}
let state=null, warning="", revision="",pendingRefresh=false;
function route(){const [page,id]=location.hash.slice(1).split("/");if(["discovery","compare","discoveries"].includes(page)){try{return{page,id:decodeURIComponent(id||"")}}catch{return{page,id:""}}}return{page:Object.hasOwn(pages,page)?page:"observatory"};}
async function compare(ids,view){
  const selected=[...new Set(ids.split(","))].slice(0,6);
  const entries=await Promise.all(selected.map(findEvent));if(!view.isConnected)return;
  if(entries.some(e=>!e))view.append(el("p","empty","Some selected recordings could not be loaded."));
  cards(entries.filter(Boolean),view);view.append(link("Back to discoveries","#discoveries"));
}
function render(){
  const {page,id}=route(), active=["discovery","compare"].includes(page)?"discoveries":page;
  const [k,t,i]=page==="compare"?["Acoustic evidence","Compare recordings","Listen to the selected recordings and inspect their individual spectra."]:page==="discovery"?["Acoustic evidence","Recording detail","Inspect the original-speed excerpt and its provenance."]:pages[active];
  byId("kicker").textContent=k;byId("title").textContent=t;byId("intro").textContent=i;document.title=t+" · Ocean Acoustics";
  for(const a of document.querySelectorAll("nav a")){if(a.hash==="#"+active)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");}
  byId("notice").textContent=warning||(!state&&["discoveries","statistics","observatory"].includes(page)?"Loading observatory data…":"");
  const view=el("div");byId("view").replaceChildren(view);
  if(page==="research")research(view);else if(page==="contribute")contribute(view);
  else if(page==="discovery")detail(id,view);
  else if(page==="compare"&&state)compare(id,view);
  else if(state)({observatory,discoveries,statistics})[page](view);
}
async function refresh(){
  try{const res=await fetch("/data/observatory.json",{cache:"no-store",signal:AbortSignal.timeout(15000)});if(!res.ok)throw Error();const next=await res.json();
    if(!next||typeof next.stats!=="object"||!Array.isArray(next.events))throw Error();
    const changed=revision!==next.generated_at||!state||warning;revision=next.generated_at;state=next;warning=Date.now()-Date.parse(next.generated_at)>900000?"Worker snapshot is over 15 minutes old. Showing the last published observation.":"";
    if(changed){if([...document.querySelectorAll("audio")].some(a=>!a.paused)){pendingRefresh=true;byId("notice").textContent="New observations will appear after playback finishes.";}else render();}
  }catch{warning=state?"Refresh unavailable. Showing the last loaded observations.":"The observation snapshot is unavailable. Research and contribution guides are available.";byId("notice").textContent=warning;}
}
function refreshAfterPlayback(){if(pendingRefresh&&![...document.querySelectorAll("audio")].some(a=>!a.paused)){pendingRefresh=false;render();}}
document.addEventListener("ended",refreshAfterPlayback,true);
window.addEventListener("hashchange",()=>{pendingRefresh=false;render();window.scrollTo(0,0);});
render();refresh();setInterval(refresh,60000);
