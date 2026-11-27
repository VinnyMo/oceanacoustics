"use strict";
const layers={
  recordings:{title:"Recordings"},
  temperature_2m:{title:"Air temperature",product:"weather",range:[-30,35]},
  wind_speed_10m:{title:"Wind speed",product:"weather",range:[0,80]},
  precipitation:{title:"Precipitation",product:"weather",range:[0,10]},
  sea_surface_temperature:{title:"Sea temperature",product:"marine",range:[-2,32]},
  ocean_current_velocity:{title:"Surface current",product:"marine",range:[0,5]},
  wave_height:{title:"Wave height",product:"marine",range:[0,8]}
};
const envNames={temperature_2m:"Air temperature",wind_speed_10m:"Wind speed",wind_direction_10m:"Wind from",
  precipitation:"Precipitation",sea_surface_temperature:"Sea-surface temperature",ocean_current_velocity:"Surface current",
  ocean_current_direction:"Current direction",wave_height:"Wave height"};
const atlas={site:"mbari/mars",clip:"",layer:"recordings",center:[-122,32],zoom:1};
let landRequest;
function envReadings(container,conditions,live=false){
  for(const [key,title] of [["weather","Atmosphere"],["marine","Ocean surface"]]){
    const r=conditions?.[key],section=el("div","model-reading");
    section.append(el("strong","",title));
    if(r){
      const ago=Date.now()-Date.parse(r.valid_at);
      section.append(el("span","small muted",(live&&ago>7200000?"Last available · ":"")+when(r.valid_at)));
      const values=Object.entries(r.values).map(([k,[v,u]])=>[envNames[k]||k,num(v,2)+" "+u]);
      if(values.length)section.append(facts(values,"env-values"));
      else section.append(el("p","small muted","No model values at this grid cell and time."));
      if(httpsUrl(r.url))section.append(link("Model data · "+r.product,httpsUrl(r.url)));
    }else section.append(el("p","small muted","Model data unavailable or awaiting retrieval."));
    container.append(section);
  }
}
function envCredit(){
  const p=el("p","small muted geo-credit");
  p.append("Surface model estimates via ",link("Open-Meteo","https://open-meteo.com/"),
    " · ",link("Model providers and attribution","https://open-meteo.com/en/docs/marine-weather-api#citation"),
    " · Copernicus Marine, C3S / ECMWF, NOAA, DWD and national weather services · ",
    link("CC BY 4.0","https://creativecommons.org/licenses/by/4.0/"));
  return p;
}
function recordingContext(ctx){
  const wrap=el("section","recording-context");
  wrap.append(el("h3","","Conditions at recording time"));
  if(ctx?.position){
    const p=ctx.position;
    wrap.append(el("p","small muted",p.lat.toFixed(3)+"°, "+p.lon.toFixed(3)+"° · "),
      link(p.basis,p.source));
  }else wrap.append(el("p","small muted","Coordinates pending verification."));
  if(ctx?.hour)wrap.append(el("p","small muted","Matched UTC hour · "+when(ctx.hour+"Z")));
  envReadings(wrap,ctx?.conditions);wrap.append(envCredit());return wrap;
}
async function globeView(view){
  const panel=el("section","atlas panel"),map=el("div","globe-stage"),side=el("div","station-side");
  const heading=el("div","atlas-head"),tools=el("div","atlas-controls");
  heading.append(el("p","label","Recording stations"),el("h2","","Acoustic globe"));
  const select=el("select"),label=el("label","","Map layer ");
  for(const [key,l] of Object.entries(layers))select.add(new Option(l.title,key));
  select.value=atlas.layer;label.append(select);tools.append(label);
  const top=el("div","atlas-top");top.append(heading,tools);
  const canvas=el("canvas");canvas.width=720;canvas.height=560;
  canvas.setAttribute("aria-label","Rotatable globe of acoustic recording stations. Select a station using the adjacent list.");
  const hint=el("div","globe-hint","Drag to rotate · Select a station");
  const zoom=el("div","globe-zoom");
  map.append(canvas,hint,zoom);const grid=el("div","atlas-grid");grid.append(map,side);panel.append(top,grid);view.append(panel);
  side.append(el("p","small muted","Loading recording stations…"));
  let sites,land,gridPoints;
  try{
    landRequest??=fetch("/land.json").then(r=>{if(!r.ok)throw Error();return r.json();}).catch(()=>{landRequest=null;return null;});
    const [data,shape]=await Promise.all([fetch("/data/globe.json",{cache:"no-store",signal:AbortSignal.timeout(12000)}).then(r=>{if(!r.ok)throw Error();return r.json();}),landRequest]);
    gridPoints=data.grid||[];sites=data.sites.map(s=>({...s,clips:s.clips.filter(c=>reviewedCatalog.has(c.id))})).filter(s=>s.clips.length);land=shape;
  }catch{side.replaceChildren(el("p","empty","The station map is awaiting a published snapshot."));return;}
  if(!view.isConnected)return;
  const projection=d3.geoOrthographic().translate([360,280]);
  const ctx=canvas.getContext("2d"),path=d3.geoPath(projection,ctx),graticule=d3.geoGraticule10();
  let hits=[],sampleHits=[];
  const sampleInfo=el("p","sample-info small muted");map.append(sampleInfo);
  function drawArrow(coords,reading,x,y,dot,pair){
      const direction=atlas.layer==="ocean_current_velocity"?reading?.values.ocean_current_direction:
        atlas.layer==="wind_speed_10m"?reading?.values.wind_direction_10m:null;
      if(direction&&pair[0]>0){
        // Project the local east/north bearing into screen space on the rotated globe.
        const angle=(direction[0]+(atlas.layer==="wind_speed_10m"?180:0))*Math.PI/180;
        const target=projection([coords[0]+.01*Math.sin(angle)/Math.max(.01,Math.cos(coords[1]*Math.PI/180)),coords[1]+.01*Math.cos(angle)]);
        const bearing=Math.atan2(target[1]-y,target[0]-x);
        ctx.save();ctx.translate(x,y);ctx.rotate(bearing);ctx.strokeStyle=dot;ctx.lineWidth=2;
        ctx.beginPath();ctx.moveTo(6,0);ctx.lineTo(22,0);ctx.lineTo(17,-4);ctx.moveTo(22,0);ctx.lineTo(17,4);ctx.stroke();ctx.restore();
      }
  }
  function draw(){
    const radius=242*atlas.zoom;
    projection.scale(radius).rotate([-atlas.center[0],-atlas.center[1]]);
    ctx.clearRect(0,0,720,560);
    function shape(obj,fill,stroke,width=1){
      ctx.beginPath();path(obj);
      if(fill){ctx.fillStyle=fill;ctx.fill();}
      if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.stroke();}
    }
    const sea=ctx.createRadialGradient(280,180,10,380,290,radius*1.2);
    sea.addColorStop(0,"#225773");sea.addColorStop(1,"#092332");
    shape({type:"Sphere"},sea,"#5697a5",1.6);
    if(land)shape(land,"#39666a","#7eaaa4",.8);
    shape(graticule,null,"rgba(144,200,210,.19)");
    hits=[];sampleHits=[];
    const layer=layers[atlas.layer];
    const color=value=>"hsl("+Math.max(15,Math.min(215,215-200*(value-layer.range[0])/(layer.range[1]-layer.range[0])))+" 78% 65%)";
    if(layer.range){
      for(const g of gridPoints){
        const r=g.current[layer.product],pair=r?.values[atlas.layer];
        if(!pair||Math.abs(Date.now()-Date.parse(r.valid_at))>14400000)continue;
        const coords=[g.position.lon,g.position.lat];
        if(d3.geoDistance(coords,atlas.center)>Math.PI/2)continue;
        const [x,y]=projection(coords);
        sampleHits.push({x,y,g,r,pair});
        ctx.fillStyle=color(pair[0]);ctx.fillRect(x-3,y-3,6,6);
        ctx.fillStyle="#b7d5df";ctx.font="11px system-ui";ctx.fillText(num(pair[0],1)+" "+pair[1],x+5,y+4);
        drawArrow(coords,r,x,y,color(pair[0]),pair);
      }
    }
    const occupied=[];
    for(const s of [...sites].sort((a,b)=>Number(b.id===atlas.site)-Number(a.id===atlas.site))){
      if(!s.position)continue;
      const coords=[s.position.lon,s.position.lat];
      if(d3.geoDistance(coords,atlas.center)>Math.PI/2)continue;
      const [x,y]=projection(coords),active=s.id===atlas.site;
      const reading=s.current[layer.product],pair=reading?.values[atlas.layer];
      const fresh=pair&&Math.abs(Date.now()-Date.parse(reading.valid_at))<7200000;
      const dot=layer.range?(fresh?color(pair[0]):"#8599a1"):"#71efd8";
      hits.push({x,y,s});
      ctx.beginPath();ctx.arc(x,y,active?7:4,0,2*Math.PI);ctx.fillStyle=dot;ctx.fill();
      if(active){ctx.strokeStyle="#fff";ctx.lineWidth=2;ctx.stroke();}
      if(fresh)drawArrow(coords,reading,x,y,dot,pair);
      if(occupied.some(([a,b])=>Math.abs(a-x)<102&&Math.abs(b-y)<18))continue;
      const text=layer.range?(fresh?num(pair[0])+" "+pair[1]:"—"):String(s.clips.length);
      ctx.font="600 14px system-ui";ctx.textBaseline="middle";ctx.strokeStyle="#071b28";ctx.lineWidth=4;
      ctx.strokeText(text,x+10,y-8);ctx.fillStyle="#f3ffff";ctx.fillText(text,x+10,y-8);occupied.push([x,y]);
    }
    hint.textContent=(layer.range?"Squares = global samples · Circles = stations · Gray = unavailable":"Numbers show playable clips")+" · Drag to rotate";
  }
  const station=el("select"),clip=el("select"),clipbox=el("div","map-clip"),conditions=el("details","station-model");
  const siteLabel=el("label","","Recording station"),clipLabel=el("label","","Recording");
  station.setAttribute("aria-label","Recording station");clip.setAttribute("aria-label","Recording");
  siteLabel.append(station);clipLabel.append(clip);side.replaceChildren(siteLabel,clipLabel,clipbox,conditions);
  const selected=()=>sites.find(s=>s.id===station.value);
  for(const s of sites.sort((a,b)=>a.name.localeCompare(b.name))){
    station.add(new Option(s.name+(/^(nrs|sanctsound)_/.test(s.id)?" ("+s.id+")":"")+" · "+s.clips.length+(s.position?"":" · unlocated"),s.id));
  }
  async function displayClip(){
    const id=atlas.clip=clip.value;clipbox.replaceChildren();
    const [event,note]=await Promise.all([findEvent(id),catalogEntry(id)]);
    if(!clipbox.isConnected||clip.value!==id)return;
    if(!event){clipbox.append(link("Recording details",detailLink({id})));return;}
    clipbox.append(el("h3","",note?.title||eventTitle(event)),player(event),link("Inspect recording →",detailLink(event)),credit(event));
    const archive=el("details","station-model");archive.append(el("summary","","Recording-hour context"),recordingContext(note?.environment));
    clipbox.append(archive);
  }
  function chooseSite(id,rotate){
    atlas.site=station.value=id;
    const s=selected();
    if(rotate&&s.position)atlas.center=[s.position.lon,s.position.lat];
    clip.replaceChildren();
    for(const c of s.clips)clip.add(new Option(c.kind+" · "+when(c.recorded_at),c.id));
    if(s.clips.some(c=>c.id===atlas.clip))clip.value=atlas.clip;
    conditions.replaceChildren(el("summary","","Latest station weather and ocean models"));
    envReadings(conditions,s.current,true);conditions.open=true;displayClip();draw();
  }
  const legend=el("div","atlas-foot");
  legend.append(el("p","small muted","Layers show timestamped station estimates and a coarse global sample grid. The recording-hour panel uses archived surface estimates."),envCredit());
  panel.append(legend);
  select.onchange=()=>{atlas.layer=select.value;sampleInfo.replaceChildren();draw();};
  station.onchange=()=>chooseSite(station.value,true);clip.onchange=displayClip;
  for(const [title,delta] of [["Zoom out",-.5],["Zoom in",.5]]){
    const btn=el("button","",delta>0?"+":"−");btn.setAttribute("aria-label",title);btn.onclick=()=>{atlas.zoom=Math.max(.8,Math.min(8,atlas.zoom+delta));draw();};zoom.append(btn);
  }
  let drag;
  canvas.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,center:[...atlas.center],moved:false};canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{
    if(!drag)return;
    const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
    if(Math.abs(dx)+Math.abs(dy)<4&&!drag.moved)return;
    drag.moved=true;const speed=130/(canvas.clientWidth/2*atlas.zoom);
    atlas.center=[drag.center[0]-dx*speed,Math.max(-89,Math.min(89,drag.center[1]+dy*speed))];draw();
  };
  canvas.onpointercancel=()=>{drag=null;};
  canvas.onpointerup=e=>{
    if(drag&&!drag.moved){
      const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left)*720/rect.width,y=(e.clientY-rect.top)*560/rect.height;
      const nearest=hits.map(h=>[Math.hypot(h.x-x,h.y-y),h.s]).sort((a,b)=>a[0]-b[0])[0];
      if(nearest&&nearest[0]<15){sampleInfo.replaceChildren();chooseSite(nearest[1].id,false);}
      else{
        const hit=sampleHits.map(h=>[Math.hypot(h.x-x,h.y-y),h]).sort((a,b)=>a[0]-b[0])[0];
        if(hit&&hit[0]<18){
          const {g,r,pair}=hit[1];
          sampleInfo.replaceChildren(layers[atlas.layer].title+" · "+num(pair[0])+" "+pair[1]+" · "+g.position.lat+"°, "+g.position.lon+"° · "+when(r.valid_at)+" · ",link("Model grid data",r.url));
        }
      }
    }drag=null;
  };
  if(!sites.length){side.replaceChildren(el("p","empty","Listening reviews are pending."));draw();return;}
  chooseSite(sites.some(s=>s.id===atlas.site)?atlas.site:sites[0].id,false);
}
