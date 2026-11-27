"use strict";
const repository = "https://github.com/VinnyMo/oceanacoustics";
const sourceRegistry = "https://registry.opendata.aws/pacific-sound/";
const byId = id => document.getElementById(id);
const pages = {
  observatory: ["Ocean Acoustics", "Observatory", "Explore recording sites, listen to underwater sounds, and compare conditions across the oceans."],
  discoveries: ["Acoustic evidence", "Discoveries", "Listen to preserved candidates and compare their acoustic signatures."],
  research: ["Acoustic field notes", "Research", "Listen to the evidence behind each open question."]
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
  const nyquist = Number.isFinite(e.sample_rate_hz) ? e.sample_rate_hz/2 : isMbari(e) ? 1000 : null;
  if (nyquist) for (const hz of [nyquist,nyquist/2,0]) {
    freq.append(el("span","",hz>=1000?num(hz/1000,2)+" kHz":num(hz)+" Hz"));
  }
  const time=el("div","time-axis");
  for(const ratio of [0,.25,.5,.75,1]) time.append(el("span","",num(e.duration_seconds*ratio)+" s"));
  plot.prepend(axis);axis.append(freq,img,time);return plot;
}
function player(e) {
  const original=media(e.audio_url), boosted=media(e.boosted_url), lowband=media(e.lowband_url);
  if (!original) return el("p","muted","Playback unavailable.");
  const wrap=el("div","clip-player"), audio=el("audio");
  audio.controls=true;audio.preload="none";
  audio.setAttribute("aria-label","Recording "+e.id);
  const choice=el("select"), label=el("label","playback-level","Playback level ");
  const levelOriginal=el("option","","Original level");levelOriginal.value=original;choice.append(levelOriginal);
  const help=el("p","figure-note");
  if(boosted){
    const gain=Number.isFinite(e.boost_gain_db)?" (+"+num(e.boost_gain_db,1)+" dB)":"";
    const levelBoost=el("option","","Boosted listening"+gain);levelBoost.value=boosted;choice.append(levelBoost);
    choice.value=boosted;help.textContent="Boost raises background noise too.";
  }
  if(lowband){
    const shifted=el("option","","Low band +220 Hz");shifted.value=lowband;choice.append(shifted);
  }
  choice.disabled=choice.options.length<2;
  function describeLevel(){
    help.textContent=lowband && choice.value===lowband
      ? "Frequency-transformed preview. The low band is shifted up by 220 Hz for small speakers."
      : boosted && choice.value===boosted ? "Boost raises background noise too." : "Original recording level.";
  }
  describeLevel();
  audio.src=choice.value;label.append(choice);wrap.append(audio,label,help);
  let pending=null;
  choice.onchange=()=>{
    describeLevel();
    const position=pending?.position??audio.currentTime;
    const playing=pending?.playing??!audio.paused;
    pending={position,playing};
    audio.src=choice.value;audio.load();
  };
  audio.addEventListener("loadedmetadata",()=>{
    if(!pending||audio.currentSrc!==choice.value)return;
    const {position,playing}=pending;pending=null;
    if(position>0)audio.currentTime=Number.isFinite(audio.duration)?Math.min(position,audio.duration):position;
    if(playing)audio.play().catch(()=>{});
  });
  audio.addEventListener("error",()=>{
    if(choice.value!==original){
      choice.selectedOptions[0].disabled=true;
      pending=pending||{position:audio.currentTime||0,playing:false};
      choice.value=original;levelOriginal.selected=true;
      choice.disabled=[...choice.options].filter(o=>!o.disabled).length===1;help.textContent="Selected preview unavailable. Original level selected.";
      audio.src=original;audio.load();
    }
  });
  return wrap;
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
function httpsUrl(value) {
  try {const url = new URL(value);return url.protocol === "https:" ? url.href : null;}
  catch {return null;}
}
function isMbari(e) {
  const url=httpsUrl(e.source_url);
  return !!url && /^pacific-sound-[a-z0-9-]+\.s3(?:[.-][a-z0-9-]+)*\.amazonaws\.com$/.test(new URL(url).hostname);
}
function eventTitle(e) {
  if(e.title)return e.title;
  if(e.classification==="Archive sample")return (e.location||e.provider||"Archive")+" excerpt";
  if(typeof e.frequency_hz==="number")return num(e.frequency_hz)+" Hz candidate";
  return e.location ? "Recording from "+e.location : "Acoustic recording";
}
function credit(e) {
  const text=el("p","small muted");
  if(e.attribution)text.append(httpsUrl(e.metadata_url)?link(e.attribution,httpsUrl(e.metadata_url)):e.attribution);
  else if(isMbari(e))text.append("Recording by Monterey Bay Aquarium Research Institute, ",link("Pacific Sound",sourceRegistry),". Original-speed excerpt and encoded playback copy under ",link("CC BY 4.0","https://creativecommons.org/licenses/by/4.0/"),".");
  else text.append("Recording attribution unavailable.");
  if(e.attribution && httpsUrl(e.license_url))text.append(" · ",link(e.license||"Source license",httpsUrl(e.license_url)));
  return text;
}
const detailLink=e=>"#discovery/"+encodeURIComponent(e.id);
function card(e,options={}) {
  const c=el("article","card"), heading=el("h3");
  c.append(el("p","label",nameOf(e)));
  heading.append(link(eventTitle(e),detailLink(e)));
  c.append(heading,el("p","small muted",when(e.recorded_at)));
  c.append(picture(e.spectrogram_url,"Spectrogram of acoustic candidate",""),player(e));
  c.append(el("p","small muted",elapsed(e.duration_seconds)+" · "+(e.location || "Location unavailable")));
  c.append(link("Inspect recording →",detailLink(e)));
  if(options.showCredit)c.append(credit(e));
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
  globeView(view);
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
  box.append(el("p","label",nameOf(e)),el("h2","",eventTitle(e)),
    el("p","sourceid",e.id),player(e),el("p","figure-note",e.station?"Playback copy of the processed archive excerpt. Original level uses the analysis signal before listening adjustments.":"Playback copy of the archived interval. Original level uses the source amplitude before listening adjustments."));
  box.append(spectrogram(e,"Relative spectral intensity · Colors scaled within this clip"),picture(e.waveform_url,"Candidate waveform","Amplitude through time"));
  box.append(facts([["Recorded",when(e.recorded_at)],["Location",e.location||"Location unavailable"],["Clip duration",elapsed(e.duration_seconds)],["Peak frequency",num(e.frequency_hz)+" Hz"],...(e.native_rate?[["Native sampling rate",num(e.native_rate,0)+" Hz"],["Analysis sampling rate",num(e.sample_rate_hz,0)+" Hz"]]:[]),["Source identifier",e.source_id],
    ...(e.source_encoding?[["Native encoding",e.source_encoding]]:[]),
    ...(e.clock_evidence||e.quality?[["Timestamp evidence",e.clock_evidence||e.quality]]:[]),
    ...(e.algorithm?[["Detector",e.algorithm]]:[]),
    ...(Number.isFinite(e.score_db)?[["Score above background",num(e.score_db,2)+" dB"]]:[]),["Review status",e.review_status||"Unreviewed"]],"measurements"));
  if(e.reference_comparison?.scores){
    const scores=e.reference_comparison.scores;
    box.append(el("h3","","Coastal reference comparison"),facts([["UF310 correlation",num(scores.UF310,3)],["UF440 correlation",num(scores.UF440,3)]]),
      el("p","small muted","Correlation compares spectral shape with two coastal development excerpts. A score alone cannot identify the sound source."));
  }
  const links=el("p","links");
  for(const [label,url] of [["Download playback audio",e.audio_url],[e.station?"Download analysis PCM (WAV)":"Download lossless excerpt",e.lossless_url]]) {
    if(media(url)){const a=link(label,media(url));a.download="";links.append(a);}
  }
  if (httpsUrl(e.source_url))links.append(link("Source archive file",httpsUrl(e.source_url)));
  links.append(link("Permanent link",detailLink(e)));
  box.append(links,credit(e));
  view.append(box);
  const c=await catalogEntry(id);
  if(!view.isConnected)return;
  if(c){
    const annotation=el("section","curator-note");
    annotation.append(el("p","label","Pip · "+c.basis),el("h3","",c.title),el("p","",c.explanation));
    if(c.note)annotation.append(facts([["Possible source",c.genre],["Working hypothesis",c.note.hypothesis],["Alternative",c.note.alternative],["Listening check",c.note.check]],"annotations"));
    box.children[2].after(annotation);
    if(c.environment)box.append(recordingContext(c.environment));
  }
  const related=e.group_id!=null?events().filter(other=>other.id!==e.id&&other.group_id===e.group_id):[];
  if (related.length) {const head=el("div","section-head");const a=link("Browse group →","#discoveries");a.onclick=()=>{group=String(e.group_id);filter=""};head.append(el("h2","","Compare recordings in this group"),a);view.append(head);cards(related.slice(0,6),view);}
}
function processingLedger(view) {
  const s=state?.stats;
  if(!s)return;
  const section=el("section","panel pad");
  section.append(el("h3","","Processing ledger"),facts([
    ["Source data processed",bytes(s.bytes_processed)],["Historical coverage",num(s.backfill_hours,3)+" h"],
    ["Processing speed",num(s.processing_speed,2)+"× real time"],["Inventoried source files",num(s.inventoried_files,0)],
    ["Storage used",bytes(s.storage_bytes)],["Worker heartbeat streak",elapsed(s.uptime_seconds)],
    ["Last successful acquisition",when(s.last_acquisition)]
  ]));
  if(events().length){
    const counts=new Map();
    for(const event of events())counts.set(nameOf(event),(counts.get(nameOf(event))||0)+1);
    section.append(el("h3","","Classification of the latest "+events().length+" candidates"),facts([...counts]));
  }
  section.append(el("p","figure-note","Ledger updated "+when(state.generated_at)));
  view.append(section);
}
function prose(view,sections) {
  const body=el("div","prose");
  for(const [title,paragraph,links] of sections){const section=el("section","panel pad");section.append(el("h2","",title),el("p","",paragraph));const items=el("div","links");for(const [label,url] of links||[])items.append(link(label,url));section.append(items);body.append(section);}
  view.append(body);
}
function methodology(view) {prose(view,[
  ["What recurs in the deep ocean?","We measure changes in underwater sound and preserve excerpts for review. Our first question is whether similar narrowband events recur across independent recording dates at the Monterey Accelerated Research System hydrophone.",[["Study protocol",repository+"/blob/main/RESEARCH.md"]]],
  ["From recording to candidate","The baseline measures spectral energy against local background. Each candidate links its analysis to an archive identifier and recording time. Human review is needed to attribute a source. A quiet analyzed interval contributes to coverage even when it yields no candidates.",[["Coverage and results","#research/coverage"],["Inspect candidates","#discoveries"]]],
  ["Coastal fish choruses","UF310 and UF440 are reference targets from California sanctuary studies. Their coastal recordings and Monterey Bay’s deep offshore observations differ in habitat, propagation and instrumentation. Frequency alone cannot identify a chorus.",[["Kim et al., ICES Journal of Marine Science","https://doi.org/10.1093/icesjms/fsag096"],["Dryad annotations","https://doi.org/10.5061/dryad.q2bvq83sw"]]],
  ["Limits of the observations","The 16 kHz source covers frequencies below 8 kHz. Earlier 2 kHz excerpts cover frequencies below 1 kHz. Weather, vessels, instruments and biological sources can produce overlapping signatures. Audited examples and independent held-out recordings are needed to estimate sensitivity and false alarms.",[["MBARI archive",sourceRegistry],["Pacific Sound documentation","https://docs.mbari.org/pacific-sound/"]]]
]);}
let researchData=null;
let researchError=false;
let researchRequest=null;
const playableEntries=items=>Array.isArray(items)?items.filter(e=>e?.id&&media(e.audio_url)):[];
function researchHeading(parent,title,count) {
  const head=el("div","section-head");
  head.append(el("h2","",title));
  if(count!=null)head.append(el("span","small muted",count+" "+(count===1?"recording":"recordings")));
  parent.append(head);
}
function reviewNote(note) {
  const e=note.event, box=el("article","panel pad review-note");
  const clip=el("div","review-clip"), heading=el("h3");
  heading.append(link(note.title||eventTitle(e),detailLink(e)));
  clip.append(el("p","label","Priority "+num(note.priority,0)+" / 5"),heading,
    el("p","small muted",[e.location,when(e.recorded_at)].filter(Boolean).join(" · ")),
    spectrogram(e,"Relative spectral intensity"),player(e),link("Recording details →",detailLink(e)),credit(e));
  const notes=el("div","review-text");
  notes.append(el("p","label","AI-assisted review"),facts([
    ["Observation",note.observation],["Working hypothesis",note.hypothesis],
    ["Alternative explanation",note.alternative],["Recommended human check",note.check]
  ],"annotations"));
  if(note.model||note.created_at)notes.append(el("p","small muted",[note.model,note.created_at&&when(note.created_at)].filter(Boolean).join(" · ")));
  box.append(clip,notes);return box;
}
const expandedProviders=new Set();
function sourceRecordings(view,data) {
  researchHeading(view,"Recording sources");
  const sources=Array.isArray(data.sources)?data.sources:[];
  if(sources.length){
    const grouped=new Map();
    for(const item of sources){
      const name=item.provider||"Other sources";
      if(!grouped.has(name))grouped.set(name,[]);
      grouped.get(name).push(item);
    }
    for(const [name,items] of grouped){
      const details=el("details","panel provider-list"), summary=el("summary");
      summary.append(el("strong","",name),el("span","small muted",items.length+" "+(items.length===1?"feed or deployment":"feeds or deployments")));
      details.append(summary);
      const list=el("ul","feed-list");
      for(const item of items){
        const row=el("li");
        row.append(el("span","",item.location||item.id),el("span","small muted",[item.status,Number.isInteger(item.clips)?num(item.clips,0)+" clips":null].filter(Boolean).join(" · ")));
        list.append(row);
      }
      details.append(list);details.open=expandedProviders.has(name);
      details.ontoggle=()=>{if(details.open)expandedProviders.add(name);else expandedProviders.delete(name);};
      view.append(details);
    }
  }else view.append(el("p","empty","Source inventory pending."));

}
function collectionInventory(view,inv){
  if(!inv)return;
  researchHeading(view,"Collection inventory");
  const matches=inv.context;
  view.append(el("p","muted",num(inv.events,0)+" stored clips · "+num(matches.located||0,0)+" located · "+
    num(matches.weather||0,0)+" with recording-hour weather · "+num(matches.marine||0,0)+" with marine data"));
  const wrap=el("div","inventory-wrap"),table=el("table","inventory"),head=table.createTHead().insertRow();
  for(const label of ["Collection","Audio type / run","Native rate","Windows or excerpts","Analyzed audio","Metered audio bytes","Recording dates (UTC)"]){
    const th=el("th","",label);th.scope="col";head.append(th);
  }
  const body=table.createTBody();
  for(const r of inv.rows){
    const row=body.insertRow();
    for(const value of [r.source,r.kind,r.rate?num(r.rate/1000,2)+" kHz":"Unknown",num(r.count,0),elapsed(r.seconds),Number.isFinite(r.bytes)?bytes(r.bytes)+(r.metered&&r.metered<r.count?" (partial)":""):"Unavailable",r.first.slice(0,10)+" – "+r.last.slice(0,10)])row.insertCell().textContent=value;
  }
  wrap.append(table);view.append(wrap,el("p","figure-note","MBARI counts processed windows, including repeated coverage at different sample rates. Other archives count screened excerpts. Date spans can contain gaps."));
}
function researchQuality(view,q) {
  if(!q)return;
  researchHeading(view,"Coverage and data quality");
  const grid=el("div","stats");
  const span=(Date.parse(q.latest_processed_at)-Date.parse(q.first_processed_at))/1000;
  const metrics=[
    ["Processing timespan",Number.isFinite(span)?elapsed(span):"Unknown"],
    ["MBARI distinct coverage",elapsed(q.distinct_seconds)],
    ["Processing effort",num(q.processed_hours,3)+" audio hours"],
    ["Provisional recurring groups",num(q.recurring_groups,0)],
    ["Candidates",num(q.candidates,0)],["Reviewed",num(q.reviewed,0)],
    ["All-zero windows",num(q.silent_windows,0)+" / "+num(q.windows,0)],
    ["Sampled feeds or deployments",num(q.sites_sampled,0)],["Source excerpts",num(q.source_samples,0)],
    ["Source screening audio",elapsed(q.source_seconds)],
    ["Source excerpts with full-scale samples",num(q.rail_samples,0)+" / "+num(q.source_quality_n,0)],
    ["All-zero source excerpts",num(q.zero_source_samples,0)+" / "+num(q.source_quality_n,0)],
    ...(Number.isInteger(q.ai_monthly_usd)?[["Pip’s budget · "+q.ai_budget_month+" UTC","$"+num(q.ai_committed_micro/1000000,3)+" of $"+num(q.ai_monthly_usd,0)+" used or reserved"]]:[["AI attempts / lifetime allowance",num(q.ai_attempts,0)+" / "+num(q.ai_limit,0)]]),
    ["AI reviews completed",num(q.ai_completed,0)]
  ];
  for(const [label,value] of metrics){
    const item=el("div","panel metric");item.append(el("small","",label),el("strong","",value));grid.append(item);
  }
  view.append(grid,el("p","figure-note","Processing timestamps · "+when(q.first_processed_at)+" to "+when(q.latest_processed_at)));
}
let showcaseIndex=null;
const browse={genre:"",mood:"",kind:"",page:0};
async function catalogEntry(id){
  try{
    const res=await fetch("/data/curation/"+encodeURIComponent(id)+".json");
    if(res.ok)return await res.json();
  }catch{}
  return null;
}
function browseShowcase(view,entries){
  const section=el("section","showcase"), tools=el("div","showcase-tools");
  researchHeading(section,"Explore the sound catalog",entries.length);
  const results=el("div","catalog"), count=el("p","small muted"), pager=el("div","links");
  count.setAttribute("role","status");
  for(const [key,label] of [["genre","Possible source"],["mood","Listening impression"],["kind","Recording type"]]){
    const field=el("label","",label),select=el("select"), totals=new Map();
    for(const e of entries)if(e[key])totals.set(e[key],1+(totals.get(e[key])||0));
    select.setAttribute("aria-label",label);
    select.add(new Option("All",""));
    for(const [v,n] of [...totals].sort(([a],[b])=>a.localeCompare(b)))select.add(new Option(v+" ("+n+")",v));
    if(!totals.has(browse[key]))browse[key]="";
    select.value=browse[key];select.onchange=()=>{browse[key]=select.value;browse.page=0;draw();};
    field.append(select);tools.append(field);
  }
  function draw(){
    const hits=entries.filter(e=>["genre","mood","kind"].every(k=>!browse[k]||e[k]===browse[k]));
    browse.page=Math.min(browse.page,Math.max(0,Math.ceil(hits.length/6)-1));
    const start=browse.page*6;
    count.textContent=hits.length?"Showing "+(start+1)+"–"+Math.min(start+6,hits.length)+" of "+hits.length+" recordings":"No recordings match these filters.";
    results.replaceChildren();pager.replaceChildren();
    for(const entry of hits.slice(start,start+6)){
      const slot=el("div","showcase-slot","Loading recording…");results.append(slot);
      Promise.all([findEvent(entry.id),catalogEntry(entry.id)]).then(([e,c])=>{
        if(!e){slot.replaceChildren(link("Open recording",detailLink(entry)));return;}
        const item=card({...e,title:c?.title||eventTitle(e)},{showCredit:true});
        item.firstChild.textContent=[c?.basis||entry.kind,c?.genre,c?.mood].filter(Boolean).join(" · ");
        if(c?.explanation)item.children[1].after(el("p","",c.explanation));
        slot.replaceChildren(item);
      });
    }
    for(const [label,delta] of [["Previous",-1],["Next",1]]){
      if(browse.page+delta<0||(browse.page+delta)*6>=hits.length)continue;
      const button=el("button","",label);button.onclick=()=>{browse.page+=delta;draw();section.scrollIntoView();};pager.append(button);
    }
  }
  section.append(tools,count,results,pager);view.append(section);draw();
}
function research(view) {
  const hero=el("section","panel pip"), portrait=el("img","portrait"), bio=el("div","pip-bio");
  portrait.src="/researcher.webp";portrait.alt="Pip, an otter wearing a laboratory coat";portrait.width=200;portrait.height=200;
  bio.append(el("p","label","Observatory researcher"),el("h2","","Pip’s listening room"),
    el("p","","Follow Pip’s picks, listen for the features he describes, and explore possible sources. Each listening note gives you an alternative explanation to test."));
  if(researchData?.status)bio.append(el("p","figure-note",researchData.status));
  hero.append(portrait,bio);view.append(hero);
  if(researchError)view.append(el("p","empty",researchData?"Could not refresh the research snapshot. Showing the last loaded notes.":"The research snapshot could not be loaded."));
  if(researchData){
    const notes=(Array.isArray(researchData.notes)?researchData.notes:[]).filter(n=>n?.event?.id&&media(n.event.audio_url)).sort((a,b)=>b.priority-a.priority);
    if(notes.length){
      researchHeading(view,"Pip’s featured recording");
      view.append(reviewNote(notes[0]));
    }
    const fallback=[...new Map([...notes.map(n=>n.event),...events(),...playableEntries(researchData.source_clips)].map(e=>[e.id,e])).values()]
      .filter(e=>media(e.audio_url)).map(e=>({id:e.id,kind:e.station?"Archive sample":"Anomaly candidate"}));
    browseShowcase(view,showcaseIndex??fallback);
    const coverage=el("section");
    coverage.id="research-coverage";
    collectionInventory(coverage,researchData.inventory);
    researchQuality(coverage,researchData.quality);
    const ledger=el("details","methods");ledger.append(el("summary","","Processing statistics and recording sources"));
    processingLedger(ledger);sourceRecordings(ledger,researchData);coverage.append(ledger);
    view.append(coverage);
    if(coverageJump && location.hash==="#research/coverage"){
      coverageJump=false;
      requestAnimationFrame(()=>coverage.scrollIntoView());
    }
    view.append(el("p","figure-note","Research snapshot · "+when(researchData.generated_at)));
  }else if(!researchError)view.append(el("p","empty","Loading research notes and recordings…"));
  const methods=el("details","methods"),summary=el("summary","","Research methods and references");methods.append(summary);methodology(methods);view.append(methods);
  if(!researchData)processingLedger(view);
  if(!researchData&&!researchError)refreshResearch();
}
async function refreshResearch() {
  if(route().page!=="research" || researchRequest)return;
  researchRequest=fetch("/data/research.json",{cache:"no-store",signal:AbortSignal.timeout(15000)});
  let changed;
  try {
    const reply=await researchRequest;
    if(!reply.ok)throw Error();
    const data=await reply.json();
    if(!Array.isArray(data.notes)||!Array.isArray(data.queue)||!Array.isArray(data.sources)||!Array.isArray(data.source_clips))throw Error();
    changed=!researchData || researchError || data.generated_at!==researchData.generated_at;
    try{
      const idx=await fetch("/data/showcase.json",{cache:"no-store",signal:AbortSignal.timeout(10000)});
      if(idx.ok){const entries=await idx.json();if(Array.isArray(entries)){changed=changed||!showcaseIndex;showcaseIndex=entries;}}
    }catch{}
    researchData=data;researchError=false;
  }catch{changed=!researchError;researchError=true;}
  finally{researchRequest=null;}
  if(changed && route().page==="research"){
    if([...document.querySelectorAll("audio")].some(a=>!a.paused))pendingRefresh=true;
    else render();
  }
}

let coverageJump=true;
let state=null, warning="", revision="",pendingRefresh=false;
function route(){const [page,id]=location.hash.slice(1).split("/");if(["discovery","compare","discoveries"].includes(page)){try{return{page,id:decodeURIComponent(id||"")}}catch{return{page,id:""}}}return{page:Object.hasOwn(pages,page)?page:"observatory"};}
async function compare(ids,view){
  const selected=[...new Set(ids.split(","))].slice(0,6);
  const entries=await Promise.all(selected.map(findEvent));if(!view.isConnected)return;
  if(entries.some(e=>!e))view.append(el("p","empty","Some selected recordings could not be loaded."));
  cards(entries.filter(Boolean),view);view.append(link("Back to discoveries","#discoveries"));
}
function render(){
  if(location.hash==="#statistics")history.replaceState(null,"","#research/coverage");
  const {page,id}=route(), active=["discovery","compare"].includes(page)?"discoveries":page;
  const [k,t,i]=page==="compare"?["Acoustic evidence","Compare recordings","Listen to the selected recordings and inspect their individual spectra."]:page==="discovery"?["Acoustic evidence","Recording detail","Inspect the original-speed excerpt and its provenance."]:pages[active];
  byId("kicker").textContent=k;byId("title").textContent=t;byId("intro").textContent=i;document.title=t+" · Ocean Acoustics";
  for(const a of document.querySelectorAll("nav a")){if(a.hash==="#"+active)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");}
  byId("notice").textContent=page==="research"?"":warning||(!state&&["discoveries","observatory"].includes(page)?"Loading observatory data…":"");
  const view=el("div");byId("view").replaceChildren(view);
  if(page==="research")research(view);
  else if(page==="discovery")detail(id,view);
  else if(page==="compare"&&state)compare(id,view);
  else if(state)({observatory,discoveries})[page](view);
}
async function refresh(){
  try{const res=await fetch("/data/observatory.json",{cache:"no-store",signal:AbortSignal.timeout(15000)});if(!res.ok)throw Error();const next=await res.json();
    if(!next||typeof next.stats!=="object"||!Array.isArray(next.events))throw Error();
    const changed=revision!==next.generated_at||!state||warning;revision=next.generated_at;state=next;warning=Date.now()-Date.parse(next.generated_at)>900000?"Worker snapshot is over 15 minutes old. Showing the last published observation.":"";
    if(changed){if([...document.querySelectorAll("audio")].some(a=>!a.paused)){pendingRefresh=true;byId("notice").textContent="New observations will appear after playback finishes.";}else render();}
  }catch{warning=state?"Refresh unavailable. Showing the last loaded observations.":"The observation snapshot is unavailable. Research remains accessible.";if(route().page!=="research")byId("notice").textContent=warning;}
}
function refreshAfterPlayback(){if(pendingRefresh&&![...document.querySelectorAll("audio")].some(a=>!a.paused)){pendingRefresh=false;render();}}
document.addEventListener("ended",refreshAfterPlayback,true);
window.addEventListener("hashchange",()=>{coverageJump=true;pendingRefresh=false;render();window.scrollTo(0,0);});
render();refresh();setInterval(()=>{refresh();refreshResearch();},60000);
