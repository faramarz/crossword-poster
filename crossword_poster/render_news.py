"""Newspaper-style crossword poster renderer (black & white / grey): grid JSON -> vector PDFs via Chromium/Playwright.

Design: full-width header (heavy condensed caps title left, byline right, rule under), solid-fill freeform grid
(every non-letter cell inside the bounding rectangle is a filled square), clue columns of one width and one gutter that
run beside the grid (wrap layout) and/or beneath it, filled by a JS column-pour with a fit loop.

Per size it writes (OUT = --outroot/<size>):
  A_black/poster.pdf (+0.125 in bleed), poster_trim.pdf, poster.png     solid black blocks      (--make A)
  B_spot/ ...                                                            black + reversed-out spot icons (--make B)
  C_grey/ ...                                                            grey blocks, saves ink  (--make C)
  key.pdf                                                                11x17 answer key (the poster, scaled, letters filled)
  fit.json                                                               chosen layout + verification report
and, once per run with --solution, OUTROOT/solution_letter.pdf/.png (letter-size filled solution).

Usage:
  python -m crossword_poster render out/grid.json --trim 24x36 --outroot out --make A,C,key --title "My Crossword"
  python -m crossword_poster render out/grid.json --solution --outroot out --title "My Crossword"
Sizes: any WxH in inches. 18x24, 24x36 and 36x48 have tuned settings; other sizes are scaled from the nearest one.
Fills: --block-fill COLOR forces one colour for every variant; otherwise A/B use black, C/key/solution use --grey-fill.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from .common import BLEED, font_face, launch, parse_size, png_preview, run_pdf

DEFAULT_TITLE = "My Crossword"
DEFAULT_BYLINE = "A custom crossword poster."

# tuned per-trim-size knobs (inches / points); other sizes are derived by scaling the nearest of these
SIZES = {
    "24x36": dict(margin=0.5, gutter=0.20, fs_min=11.0, fs_max=18.0, cell_min=0.45, rule=3.0, sw=1.0, outer=3.0, clue_weight=400, tmax=140),
    "18x24": dict(margin=0.5, gutter=0.15, fs_min=8.0, fs_max=14.0, cell_min=0.33, rule=2.5, sw=0.75, outer=2.5, clue_weight=500, tmax=110),
    "36x48": dict(margin=0.75, gutter=0.30, fs_min=16.5, fs_max=27.0, cell_min=0.675, rule=4.5, sw=1.5, outer=4.5, clue_weight=400, tmax=210),
}


def size_config(trim):
    """Settings for a trim size 'WxH'. Tuned entries are used verbatim; anything else scales the nearest base by width."""
    key = trim.lower().replace("×", "x")
    w, h = parse_size(key)
    for name, cfg in SIZES.items():
        if parse_size(name) == (w, h):
            return dict(cfg)
    base_name = min(SIZES, key=lambda n: abs(parse_size(n)[0] - w))
    k = w / parse_size(base_name)[0]
    b = SIZES[base_name]
    out = dict(b)
    for f in ("margin", "gutter", "fs_min", "fs_max", "cell_min", "rule", "sw", "outer", "tmax"):
        out[f] = round(b[f] * k, 4)
    out["margin"] = max(out["margin"], 0.3)
    return out


# --------------------------------------------------------------- grid / clues (copied from render.py, trimmed)
def analyse(gj):
    g = gj["grid"]
    R, C = len(g), len(g[0])
    cells = {(r, c): (g[r][c] or "").upper() for r in range(R) for c in range(C) if (g[r][c] or "").strip()}
    has = lambda r, c: (r, c) in cells
    nums, entries, n = {}, [], 0
    for r in range(R):
        for c in range(C):
            if not has(r, c):
                continue
            sa = (not has(r, c - 1)) and has(r, c + 1)
            sd = (not has(r - 1, c)) and has(r + 1, c)
            if not (sa or sd):
                continue
            n += 1
            nums[(r, c)] = n
            for d, ok, dr, dc in (("across", sa, 0, 1), ("down", sd, 1, 0)):
                if ok:
                    w, rr, cc = "", r, c
                    while has(rr, cc):
                        w += cells[(rr, cc)]
                        rr += dr
                        cc += dc
                    entries.append(dict(number=n, direction=d, answer=w, row=r, col=c))
    by = {(str(x["direction"]).lower(), int(x["number"])): x for x in gj["clues"]}
    for e in entries:
        x = by[(e["direction"], e["number"])]
        assert re.sub(r"[^A-Z]", "", x["answer"].upper()) == e["answer"], (e, x)
        t = re.sub(r"\s+", " ", x["clue"]).strip()
        if not re.search(r"\(\d+(,\d+)*\)\s*$", t):
            t += f" ({len(e['answer'])})"
        e["text"] = t
        e["id"] = x.get("id") or x.get("source")
    assert len(entries) == len(gj["clues"]) == len(by), (len(entries), len(gj["clues"]))
    return dict(rows=R, cols=C, cells=cells, nums=nums, entries=entries)


# ------------------------------------------------------------------- spot illustrations
def find_voids(an, minw=3, minh=3, k=8):
    """Largest rectangles made only of non-letter (black) cells, greedy, disjoint."""
    R, C = an["rows"], an["cols"]
    empty = [[(r, c) not in an["cells"] for c in range(C)] for r in range(R)]
    used = [[False] * C for _ in range(R)]
    res = []
    for _ in range(k):
        best = None
        h = [0] * C
        for r in range(R):
            for c in range(C):
                h[c] = h[c] + 1 if empty[r][c] and not used[r][c] else 0
            st = []
            for c in range(C + 1):
                cur = h[c] if c < C else 0
                start = c
                while st and st[-1][1] >= cur:
                    s, hh = st.pop()
                    w = c - s
                    if w >= minw and hh >= minh:
                        # prefer big area, break ties toward squarer
                        key = (w * hh, -abs(w - hh))
                        if best is None or key > best[0]:
                            best = (key, r - hh + 1, s, hh, w)
                    start = s
                st.append((start, cur))
        if not best:
            break
        _, r0, c0, hh, w = best
        res.append(dict(r=r0, c=c0, h=hh, w=w))
        for r in range(r0 - 1, r0 + hh + 1):          # keep a one-cell moat between chosen voids
            for c in range(c0 - 1, c0 + w + 1):
                if 0 <= r < R and 0 <= c < C:
                    used[r][c] = True
    return res


def pick_icons(an, n=3, spot_text=""):
    """Choose up to n voids spread over the grid and assign an icon each (widest void -> the optional spot text,
    squarer -> cake / hat). With no spot text only the cake and the hat are used."""
    voids = find_voids(an)
    if not voids:
        return []
    R, C = an["rows"], an["cols"]
    chosen = [voids[0]]
    for v in voids[1:]:
        if len(chosen) >= n:
            break
        # spread: require some distance from already chosen
        cx, cy = v["c"] + v["w"] / 2, v["r"] + v["h"] / 2
        if all(((cx - (u["c"] + u["w"] / 2)) / C) ** 2 + ((cy - (u["r"] + u["h"] / 2)) / R) ** 2 > 0.06 for u in chosen):
            chosen.append(v)
    for v in voids:
        if len(chosen) >= n:
            break
        if v not in chosen:
            chosen.append(v)
    chosen.sort(key=lambda v: -(v["w"] / v["h"]))   # widest first
    kinds = ["text", "cake", "hat"] if spot_text else ["cake", "hat"]
    out = []
    for kind, v in zip(kinds, chosen):
        out.append(dict(kind=kind, x=v["c"], y=v["r"], w=v["w"], h=v["h"], text=spot_text))
    return out


# ----------------------------------------------------------------------- HTML
def font_faces():
    return "\n".join([
        font_face("Archivo Narrow", "ArchivoNarrow", "ArchivoNarrow-Regular.ttf", 400),
        font_face("Archivo Narrow", "ArchivoNarrow", "ArchivoNarrow-Medium.ttf", 500),
        font_face("Archivo Narrow", "ArchivoNarrow", "ArchivoNarrow-Bold.ttf", 700),
        font_face("Oswald", "Oswald", "Oswald-Bold.ttf", 700),
    ])


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>poster</title><style>
__FONTS__
@page{size:__PW__in __PH__in;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:__PW__in;height:__PH__in;overflow:hidden;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:'Archivo Narrow',sans-serif;color:#000}
#page{position:absolute;left:0;top:0;width:__PW__in;height:__PH__in;overflow:hidden}
#sheet{position:absolute;left:0;top:0;width:__PW__in;height:__PH__in;background:#fff;transform-origin:0 0}
#box{position:absolute;left:__OX__in;top:__OY__in;width:__CW__in;height:__CH__in}
#hdr{position:absolute;left:0;top:0;width:__CW__in;display:flex;justify-content:space-between;align-items:last baseline;
     border-bottom:__RULE__pt solid #000;padding-bottom:.1em;gap:.35in;}
#hdr h1{flex:none;font:700 100pt/.9 'Oswald',sans-serif;text-transform:uppercase;letter-spacing:.012em;white-space:nowrap;}
#hdr .by{flex:none;font:500 24pt/1.12 'Archivo Narrow',sans-serif;text-align:right;text-wrap:balance;}
#gridbox{position:absolute}
#gridbox svg{display:block;overflow:visible}
.col{position:absolute;display:flex;flex-direction:column;overflow:visible}
.clue,#meas .clue{display:grid;grid-template-columns:1.5em 1fr;column-gap:.3em;line-height:var(--lh,1.07);font-family:'Archivo Narrow',sans-serif;font-weight:__CW8__;}
.clue .n{font-weight:700;text-align:right;}
.clue .t{min-width:0;overflow-wrap:break-word;hyphens:manual;text-wrap:pretty;}
.hd{font:700 1.5em/1 'Oswald',sans-serif;letter-spacing:.07em;text-transform:uppercase;border-bottom:1.6pt solid #000;padding-bottom:.12em;}
#meas{position:absolute;left:-20000px;top:0;visibility:hidden}
#meas .hd,#meas .clue{display:grid}
</style></head><body><div id="page"><div id="sheet"><div id="box">
<div id="hdr"><h1 id="ttl"></h1><div class="by" id="by"></div></div>
<div id="gridbox"></div><div id="clues"></div>
</div></div></div><div id="meas"></div>
<script>
const D=__DATA__;
const IN=96,PT=96/72,NS='http://www.w3.org/2000/svg';
const $=id=>document.getElementById(id);
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
const items=[];
for(const dir of ['across','down']){
  items.push({head:true,label:dir.toUpperCase()});
  D.entries.filter(e=>e.direction===dir).sort((a,b)=>a.number-b.number).forEach(e=>items.push({head:false,e}));
}
const itemHTML=it=>it.head?`<div class="hd">${it.label}</div>`:`<div class="clue"><span class="n">${it.e.number}</span><span class="t">${esc(it.e.text)}</span></div>`;
$('meas').innerHTML=items.map(itemHTML).join('');
$('ttl').textContent=D.title; $('by').textContent=D.key?('Answer key. '+D.byline):D.byline;
const Wpx=D.W*IN, Hpx=D.H*IN, Gpx=D.g*IN;

/* ---------- header: biggest title that leaves room for the byline on one line ---------- */
function buildHeader(frac,Tfix){
  const h=$('hdr'),t=$('ttl'),b=$('by');
  let T=D.tmax*frac;
  const set=T=>{t.style.fontSize=T+'pt';b.style.fontSize=(T*D.byRatio)+'pt';b.style.width=(T*D.byRatio*D.byEm)+'pt';};
  if(Tfix){T=Tfix;set(T);return {T,h:h.getBoundingClientRect().height};}
  set(T);
  while(h.scrollWidth>h.clientWidth+0.5&&T>16){T-=0.25;set(T);}
  return {T,h:h.getBoundingClientRect().height};
}

/* ---------- grid (SVG, pt units) ---------- */
function drawGrid(cell,yG,Wg){
  /* Wg = total box width in inches INCLUDING the outer frame; the frame sits OUTSIDE the cell area and the viewBox is padded by it,
     so no cell stroke is ever clipped and the frame never covers a cell interior. */
  const cpt=cell*72,W=D.cols*cpt,H=D.rows*cpt,sw=D.sw,o=D.outer;
  const gb=$('gridbox');gb.style.left=(Wpx-Wg*IN)+'px';gb.style.top=yG+'px';
  const svg=document.createElementNS(NS,'svg');
  svg.setAttribute('width',(W+2*o)+'pt');svg.setAttribute('height',(H+2*o)+'pt');svg.setAttribute('viewBox',`${-o} ${-o} ${W+2*o} ${H+2*o}`);
  let s=`<rect x="0" y="0" width="${W}" height="${H}" fill="${D.blockFill||'#000'}"/>`;
  for(const c of D.cells) s+=`<rect x="${c.c*cpt}" y="${c.r*cpt}" width="${cpt}" height="${cpt}" fill="#fff"/>`;
  s+=`<g fill="none" stroke="#000" stroke-width="${sw}">`;
  for(const c of D.cells) s+=`<rect x="${c.c*cpt}" y="${c.r*cpt}" width="${cpt}" height="${cpt}"/>`;
  s+='</g>';
  /* spot illustrations: white, reversed out of black voids only */
  if(D.icons&&D.icons.length) for(const ic of D.icons) s+=icon(ic,cpt);
  const np=cpt*D.numRatio;
  for(const c of D.cells){
    const x=c.c*cpt,y=c.r*cpt;
    if(c.n) s+=`<text x="${x+cpt*0.07}" y="${y+np*0.88+cpt*0.04}" font-family="Archivo Narrow" font-weight="700" font-size="${np}" fill="#000">${c.n}</text>`;
    if(D.key) s+=`<text x="${x+cpt*0.5}" y="${y+cpt*0.84}" text-anchor="middle" font-family="Archivo Narrow" font-weight="700" font-size="${cpt*0.6}" fill="#000">${c.l}</text>`;
  }
  s+=`<rect x="${-o/2}" y="${-o/2}" width="${W+o}" height="${H+o}" fill="none" stroke="#000" stroke-width="${o}"/>`;
  svg.innerHTML=s;gb.innerHTML='';gb.appendChild(svg);
  fixIcons(svg);
  return {w:(W+2*o)/72,h:(H+2*o)/72};
}
function icon(ic,cpt){
  const m=0.22*cpt,x=ic.x*cpt+m,y=ic.y*cpt+m,w=ic.w*cpt-2*m,h=ic.h*cpt-2*m;
  const st='stroke="#fff" fill="none" stroke-linecap="round" stroke-linejoin="round"';
  let body='',bw=100,bh=100,bx=0,by=0;
  if(ic.kind==='text'){
    return `<text class="spottext" data-box="${x},${y},${w},${h}" font-family="Oswald" font-weight="700" font-size="100" fill="#fff">${esc(ic.text)}</text>`;
  }
  if(ic.kind==='cake'){
    bx=2;by=8;bw=96;bh=84;
    body=`<g ${st} stroke-width="4.2"><rect x="10" y="56" width="80" height="30"/><rect x="28" y="36" width="44" height="20"/>
      <path d="M10 64q5 7 10 0t10 0t10 0t10 0t10 0t10 0t10 0t10 0"/><path d="M2 91H98"/>
      <path d="M38 36V24M50 36V22M62 36V24"/></g>
      <g fill="#fff"><path d="M38 12q4 5 0 8q-4-3 0-8zM50 10q4 5 0 8q-4-3 0-8zM62 12q4 5 0 8q-4-3 0-8z"/></g>`;
  } else {
    bx=10;by=2;bw=80;bh=90;
    body=`<g ${st} stroke-width="4.2"><path d="M50 14L84 88H16Z"/><path d="M39 42H61M30 62H70"/><path d="M12 88H88"/></g>
      <g fill="#fff"><circle cx="50" cy="9" r="7"/><circle cx="45" cy="76" r="2.6"/><circle cx="55" cy="76" r="2.6"/><circle cx="50" cy="52" r="2.6"/></g>`;
  }
  const k=Math.min(w/bw,h/bh),tx=x+(w-bw*k)/2-bx*k,ty=y+(h-bh*k)/2-by*k;
  return `<g transform="translate(${tx} ${ty}) scale(${k})">${body}</g>`;
}
function fixIcons(svg){
  svg.querySelectorAll('text.spottext').forEach(t=>{
    const [x,y,w,h]=t.dataset.box.split(',').map(Number);
    const bb=t.getBBox();
    const k=Math.min(w/bb.width,h/bb.height);
    const tx=x+(w-bb.width*k)/2-bb.x*k,ty=y+(h-bb.height*k)/2-bb.y*k;
    t.setAttribute('transform',`translate(${tx} ${ty}) scale(${k})`);
    t.removeAttribute('data-box');
  });
}

/* ---------- measuring + the column pour ---------- */
const mcache={};
function measure(wcPx,fs,lh){
  lh=lh||1.07;
  const key=wcPx+'|'+fs+'|'+lh;
  if(mcache[key])return mcache[key];
  const m=$('meas');m.style.width=wcPx+'px';m.style.fontSize=fs+'pt';m.style.setProperty('--lh',lh);
  const ch=m.children,hs=new Array(ch.length);
  for(let i=0;i<ch.length;i++)hs[i]=ch[i].getBoundingClientRect().height;
  return mcache[key]=hs;
}
function gaps(fs,lh){const f=fs*PT,k=(lh||1.07)/1.07;return{c:D.gapC*f*k,afterHead:D.gapH*f*k,beforeHead:D.gapB*f*k};}
function pour(hs,fs,cols,lh){
  const g=gaps(fs,lh),N=items.length,placed=cols.map(()=>[]),used=cols.map(()=>0);
  let ci=0;
  for(let i=0;i<N;i++){
    const head=items[i].head;
    // a heading travels with its next two clues (never a widow at a column foot)
    let need=hs[i];
    if(head){need+=g.afterHead+(i+1<N?hs[i+1]:0)+(i+2<N?g.c+hs[i+2]:0);}
    for(;;){
      if(ci>=cols.length)return{ok:false,at:i,placed,used};
      const first=placed[ci].length===0;
      const prev=first?null:items[placed[ci][placed[ci].length-1].i];
      const gap=first?0:(head?g.beforeHead:(prev.head?g.afterHead:g.c));
      if(used[ci]+gap+need<=cols[ci].cap+0.01){
        placed[ci].push({i,gap,h:hs[i]});used[ci]+=gap+hs[i];break;
      }
      ci++;
    }
  }
  return{ok:true,placed,used};
}
function planGeom(kT,m,yG,hdrH){
  const wc=(Wpx-(kT-1)*Gpx)/kT,Wg=m*wc+(m-1)*Gpx,oIn=D.outer/72,cell=(Wg/IN-2*oIn)/D.cols,Hg=(cell*D.rows+2*oIn)*IN,kL=kT-m;
  const yU=yG+Hg+Gpx,capU=Hpx-yU;
  const cols=[];
  for(let j=0;j<kL;j++)cols.push({x:j*(wc+Gpx),y:yG,cap:Hg,kind:'L'});
  for(let j=0;j<kT;j++)cols.push({x:j*(wc+Gpx),y:yU,cap:capU,kind:'U'});
  return{kT,m,kL,wc,Wg:Wg/IN,cell,Hg:Hg/IN,yG,yU,capU,cols,ok:capU>0};
}
function feasible(P,fs,lh){
  if(!P.ok)return false;
  const hs=measure(P.wc,fs,lh);
  return pour(hs,fs,P.cols,lh).ok;
}
function maxLh(P,fs){
  let lo=1.07,hi=D.lhMax;
  if(feasible(P,fs,hi))return hi;
  for(let k=0;k<9;k++){const mid=Math.round((lo+hi)/2*1000)/1000;if(mid<=lo||mid>=hi)break;if(feasible(P,fs,mid))lo=mid;else hi=mid;}
  let v=Math.floor(lo*1000)/1000;
  while(v>1.07&&!feasible(P,fs,v))v=Math.round((v-0.001)*1000)/1000;
  return Math.max(1.07,v);
}
function maxFs(P){
  const wcpt=P.wc/PT;
  let hi=Math.min(D.fsMax,wcpt/D.minRatio),lo=D.fsMin;
  if(hi<lo)return null;
  if(!feasible(P,lo))return null;
  if(feasible(P,hi))return hi;
  for(let k=0;k<9;k++){const mid=Math.round((lo+hi)/2*100)/100;if(mid<=lo||mid>=hi)break;if(feasible(P,mid))lo=mid;else hi=mid;}
  // the pour is not perfectly monotone: probe a little above
  let best=lo;for(let s=Math.round((lo+0.05)*100)/100;s<=Math.min(lo+0.6,D.fsMax);s=Math.round((s+0.05)*100)/100){if(feasible(P,s))best=s;}
  let v=Math.floor(best*20)/20;
  while(v>D.fsMin&&!feasible(P,v))v=Math.round((v-0.05)*100)/100;
  return feasible(P,v)?v:null;
}
function fitAll(){
  const log=[];
  for(const frac of D.tfracs){
    const hd=buildHeader(frac),yG=hd.h+Gpx;
    const cands=[];
    for(let kT=3;kT<=22;kT++){
      const wcpt=((Wpx-(kT-1)*Gpx)/kT)/PT;
      if(wcpt<D.fsMin*D.minRatio||wcpt>D.fsMax*D.maxRatio*1.0+D.fsMin*0) continue;
      for(let m=kT;m>=1;m--){
        const P=planGeom(kT,m,yG,hd.h);
        if(P.cell<D.cellMin-1e-9)break;
        if(m<kT&&D.mode==='full')continue;
        cands.push(P);
      }
    }
    cands.sort((a,b)=>b.cell-a.cell);
    const feas=[];let topCell=0;
    for(const P of cands){
      if(P.cell<topCell*0.985)break;
      const fs=maxFs(P);
      log.push({kT:P.kT,m:P.m,cell:+P.cell.toFixed(4),fs});
      if(fs===null)continue;
      topCell=Math.max(topCell,P.cell);feas.push(Object.assign({},P,{fs}));
    }
    let best=null;
    for(const P of feas){if(P.cell>=topCell*0.985&&(!best||P.fs>best.fs||(P.fs===best.fs&&P.cell>best.cell)))best=P;}
    if(best)return{ok:true,frac,T:hd.T,hdrH:hd.h,kT:best.kT,m:best.m,kL:best.kL,cell:best.cell,fs:best.fs,lh:maxLh(best,best.fs),log};
  }
  return{ok:false,log};
}

/* ---------- apply a plan ---------- */
function applyPlan(F){
  const hd=buildHeader(F.frac,F.T);
  const yG=hd.h+Gpx,P=planGeom(F.kT,F.m,yG,hd.h);
  const g=drawGrid(P.cell,yG,P.Wg);
  const hs=measure(P.wc,F.fs,F.lh);
  // balance: the largest common shortfall d that still pours, so every column ends at about the same height
  let lo=0,hi=Math.max(...P.cols.map(c=>c.cap))*0.5;
  const shr=d=>P.cols.map(c=>Object.assign({},c,{cap:c.cap-d}));
  for(let k=0;k<14;k++){const mid=(lo+hi)/2;if(pour(hs,F.fs,shr(mid),F.lh).ok)lo=mid;else hi=mid;}
  const res=pour(hs,F.fs,shr(lo),F.lh);
  if(!res.ok)throw new Error('plan no longer pours (non-monotone fit)');
  const cl=$('clues');cl.innerHTML='';
  const gp=gaps(F.fs,F.lh);
  let slackInfo=[];
  res.placed.forEach((list,ci)=>{
    const col=P.cols[ci];
    if(!list.length)return;
    const div=document.createElement('div');div.className='col';
    div.style.cssText=`left:${col.x}px;top:${col.y}px;width:${P.wc}px;height:${col.cap}px;font-size:${F.fs}pt;--lh:${F.lh}`;
    // vertical justification: spread leftover height over clue-to-clue gaps so column feet line up
    const slack=col.cap-res.used[ci];
    const nj=list.filter((p,k)=>k>0&&!items[p.i].head&&!items[list[k-1].i].head).length;
    const per=nj?slack/nj:0;
    const justify=nj&&per<=D.maxJust*gp.c&&slack>=0;
    slackInfo.push({col:ci,kind:col.kind,slack:+slack.toFixed(1),n:list.length,justified:!!justify});
    list.forEach((p,k)=>{
      const it=items[p.i];const w=document.createElement('div');w.innerHTML=itemHTML(it);
      const node=w.firstChild;
      const extra=(justify&&k>0&&!it.head&&!items[list[k-1].i].head)?per:0;
      node.style.marginTop=(p.gap+extra)+'px';
      node.dataset.i=p.i;node.dataset.ci=ci;
      div.appendChild(node);
    });
    cl.appendChild(div);
  });
  const mm=$('meas');if(mm)mm.remove();
  return{P,res,slackInfo};
}

/* ---------- verification ---------- */
function verify(F){
  const out={ok:true,problems:[]};
  const cl=[...document.querySelectorAll('#clues .clue')];
  const heads=[...document.querySelectorAll('#clues .hd')];
  const box=$('box').getBoundingClientRect();
  out.nClues=cl.length;out.nHeads=heads.length;
  const ids=cl.map(c=>+c.dataset.i);
  const seen=new Set(ids);
  if(cl.length!==D.entries.length||seen.size!==cl.length){out.ok=false;out.problems.push('clue count/duplicates');}
  const gr=document.querySelector('#gridbox svg').getBoundingClientRect();
  out.grid={x:(gr.left-box.left)/IN,y:(gr.top-box.top)/IN,w:gr.width/IN,h:gr.height/IN};
  if(gr.right>box.right+0.6||gr.left<box.left-0.6||gr.bottom>box.bottom+0.6){out.ok=false;out.problems.push('grid outside box');}
  const colEls=[...document.querySelectorAll('#clues .col')];
  let minFoot=1e9;
  for(const c of colEls){
    const cr=c.getBoundingClientRect();
    const kids=[...c.children];
    if(kids.length&&kids[kids.length-1].classList.contains('hd')){out.ok=false;out.problems.push('heading at column foot');}
    for(const k of kids){
      const r=k.getBoundingClientRect();
      if(r.bottom>cr.bottom+0.75||r.top<cr.top-0.75){out.ok=false;out.problems.push('overflow col '+k.dataset.i);}
      const t=k.querySelector('.t');if(t&&t.scrollWidth>t.clientWidth+0.5){out.ok=false;out.problems.push('wide text '+k.dataset.i);}
      // overlap with grid
      if(r.left<gr.right-0.5&&r.right>gr.left+0.5&&r.top<gr.bottom-0.5&&r.bottom>gr.top+0.5){out.ok=false;out.problems.push('clue over grid '+k.dataset.i);}
    }
    const last=kids[kids.length-1];if(last)minFoot=Math.min(minFoot,(cr.bottom-last.getBoundingClientRect().bottom)/IN);
  }
  out.maxFootGapIn=minFoot;
  // single-column membership: each clue is one block in exactly one column (blocks cannot be split by construction)
  const tr=$('hdr').getBoundingClientRect();
  out.header={w:tr.width/IN,h:tr.height/IN,ttlPt:parseFloat($('ttl').style.fontSize),byPt:parseFloat($('by').style.fontSize),
    fits:$('hdr').scrollWidth<=$('hdr').clientWidth+0.5};
  if(!out.header.fits){out.ok=false;out.problems.push('header overflow');}
  const lastY=Math.max(...colEls.map(c=>{const k=c.lastElementChild;return k?k.getBoundingClientRect().bottom:0;}));
  out.contentBottomIn=(lastY-box.top)/IN;out.boxH=D.H;
  return out;
}
window.__ready=false;
document.fonts.ready.then(async()=>{
  await Promise.all(['700 20px Oswald','400 20px "Archivo Narrow"','500 20px "Archivo Narrow"','700 20px "Archivo Narrow"'].map(f=>document.fonts.load(f)));
  window.__ready=true;
});
</script></body></html>"""


SOLUTION_PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>solution</title><style>
__FONTS__
@page{size:__PW__in __PH__in;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:__PW__in;height:__PH__in;overflow:hidden;background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
#box{position:absolute;left:__M__in;top:__M__in;width:__CW__in;height:__CH__in}
#hdr{position:absolute;left:0;top:0;width:__CW__in;border-bottom:2.25pt solid #000;padding-bottom:.1em}
#hdr h1{display:inline-block;font:700 40pt/.9 'Oswald',sans-serif;text-transform:uppercase;letter-spacing:.012em;white-space:nowrap}
#gridbox{position:absolute}#gridbox svg{display:block;overflow:visible}
</style></head><body><div id="box"><div id="hdr"><h1 id="ttl"></h1></div><div id="gridbox"></div></div>
<script>
const D=__DATA__;const NS='http://www.w3.org/2000/svg';const IN=96;
document.getElementById('ttl').textContent=D.title;
document.fonts.ready.then(async()=>{
  await Promise.all(['700 20px Oswald','700 20px "Archivo Narrow"'].map(f=>document.fonts.load(f)));
  const h=document.getElementById('hdr'),t=document.getElementById('ttl');
  let T=60;t.style.fontSize=T+'pt';
  while(t.scrollWidth>h.clientWidth+0.5&&T>12){T-=0.25;t.style.fontSize=T+'pt';}
  const hh=h.getBoundingClientRect().height;
  const g=0.12*IN,availH=D.H*IN-hh-g,availW=D.W*IN;
  const oIn=D.outer/72,cell=Math.min((availW/IN-2*oIn)/D.cols,(availH/IN-2*oIn)/D.rows);           // inches, frame excluded
  const cpt=cell*72,W=D.cols*cpt,H=D.rows*cpt,sw=D.sw,o=D.outer,np=cpt*D.numRatio;const WT=W+2*o,HT=H+2*o;
  const gb=document.getElementById('gridbox');
  const free=Math.max(0,D.H*IN-(hh+g+HT/72*IN)),off=free/2;
  document.getElementById('hdr').style.top=off+'px';
  gb.style.left=((availW-WT/72*IN)/2)+'px';gb.style.top=(off+hh+g)+'px';
  const svg=document.createElementNS(NS,'svg');svg.setAttribute('width',WT+'pt');svg.setAttribute('height',HT+'pt');svg.setAttribute('viewBox',`${-o} ${-o} ${WT} ${HT}`);
  let s=`<rect x="0" y="0" width="${W}" height="${H}" fill="${D.blockFill||'#000'}"/>`;
  for(const c of D.cells)s+=`<rect x="${c.c*cpt}" y="${c.r*cpt}" width="${cpt}" height="${cpt}" fill="#fff"/>`;
  s+=`<g fill="none" stroke="#000" stroke-width="${sw}">`;
  for(const c of D.cells)s+=`<rect x="${c.c*cpt}" y="${c.r*cpt}" width="${cpt}" height="${cpt}"/>`;
  s+='</g>';
  for(const c of D.cells){const x=c.c*cpt,y=c.r*cpt;
    if(c.n)s+=`<text x="${x+cpt*0.07}" y="${y+np*0.88+cpt*0.04}" font-family="Archivo Narrow" font-weight="700" font-size="${np}">${c.n}</text>`;
    s+=`<text x="${x+cpt*0.5}" y="${y+cpt*0.84}" text-anchor="middle" font-family="Archivo Narrow" font-weight="700" font-size="${cpt*0.6}">${c.l}</text>`;}
  s+=`<rect x="${-o/2}" y="${-o/2}" width="${W+o}" height="${H+o}" fill="none" stroke="#000" stroke-width="${o}"/>`;
  svg.innerHTML=s;gb.appendChild(svg);
  window.__info={cell,titlePt:T,hdrH:hh/IN,gridW:WT/72,gridH:HT/72};window.__done=true;
});
</script></body></html>"""


def _js_json(obj):
    """JSON safe to embed inside a <script> element."""
    return json.dumps(obj).replace("</", "<\\/").replace("<!--", "<\\!--")


def build_data(an, tcfg, cw, ch, key=False, icons=None, fill="#000000", title=DEFAULT_TITLE, byline=DEFAULT_BYLINE):
    cells = [dict(r=r, c=c, l=l, n=an["nums"].get((r, c), 0)) for (r, c), l in sorted(an["cells"].items())]
    return dict(
        rows=an["rows"], cols=an["cols"], cells=cells, entries=an["entries"], key=key, icons=icons or [], blockFill=fill,
        W=cw, H=ch, g=tcfg["gutter"], fsMin=tcfg["fs_min"], fsMax=tcfg["fs_max"], cellMin=tcfg["cell_min"],
        sw=tcfg["sw"], outer=tcfg["outer"], numRatio=0.27, tmax=tcfg["tmax"], byRatio=0.25, byEm=13.0,
        title=title, byline=byline,
        tfracs=tcfg.get("tfracs", [1.0, 0.9, 0.8, 0.7, 0.6]), mode=tcfg.get("mode", "any"),
        minRatio=11.0, maxRatio=30.0, gapC=0.26, gapH=0.5, gapB=1.0, lhMax=1.22, maxJust=1.6,
    )


def build_poster_html(data, trim, bleed, tcfg, fit=None):
    tw, th = trim
    pw, ph = tw + 2 * bleed, th + 2 * bleed
    m = tcfg["margin"]
    d = dict(data)
    if fit:
        d["fit"] = fit
    page = (PAGE.replace("__FONTS__", font_faces()).replace("__PW__", str(pw)).replace("__PH__", str(ph))
            .replace("__OX__", str(bleed + m)).replace("__OY__", str(bleed + m))
            .replace("__CW__", str(tw - 2 * m)).replace("__CH__", str(th - 2 * m))
            .replace("__RULE__", str(tcfg["rule"])).replace("__CW8__", str(tcfg["clue_weight"]))
            .replace("__DATA__", _js_json(d)))
    return page


def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster render", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("grid", help="grid JSON with a top-level 'clues' array (from `build` / `generate` + `attach_pool`)")
    ap.add_argument("--trim", default="24x36", help="trim size WxH in inches (default 24x36; tuned: 18x24, 24x36, 36x48)")
    ap.add_argument("--outroot", default=".")
    ap.add_argument("--make", default="A,B,C,key", help="comma list: A (A_black), B (B_spot: black + white icons), C (C_grey), key (grey 11x17 key)")
    ap.add_argument("--block-fill", default=os.environ.get("BLOCK_FILL") or None, metavar="COLOR",
                    help="CSS colour for the non-letter squares in EVERY variant (A, B, C, key, solution). "
                         "Default: A/B black, C/key/solution --grey-fill. Env BLOCK_FILL is also honoured.")
    ap.add_argument("--grey-fill", default="#a3a3a3", help="non-letter squares in C_grey, the key and the solution when --block-fill is not given (a deliberate tint, 36%% black)")
    ap.add_argument("--title", default=DEFAULT_TITLE, help="poster title (default: %(default)r)")
    ap.add_argument("--byline", "--subtitle", dest="byline", default=DEFAULT_BYLINE, help="line to the right of the title (default: %(default)r)")
    ap.add_argument("--spot-text", default="", help="short text (e.g. a number) reversed out of the widest black void in variant B; default none")
    ap.add_argument("--quiet", action="store_true", help="print only the one-line fit summary")
    ap.add_argument("--solution", action="store_true", help="write OUTROOT/solution_letter.pdf/.png (no poster)")
    ap.add_argument("--mode", default="any", choices=["any", "full"], help="'full' forbids the wrap layout")
    ap.add_argument("--png-width", type=int, default=1200)
    ap.add_argument("--build-dir", default=None, help="scratch HTML directory (default OUTROOT/.build)")
    a = ap.parse_args(argv)
    a.build_dir = a.build_dir or os.path.join(a.outroot, ".build")
    fill_dark = a.block_fill or "#000000"
    fill_grey = a.block_fill or a.grey_fill

    from playwright.sync_api import sync_playwright
    gj = json.load(open(a.grid))
    an = analyse(gj)
    os.makedirs(a.build_dir, exist_ok=True)
    report = dict(grid=f"{an['cols']}x{an['rows']}", entries=len(an["entries"]))

    with sync_playwright() as pw:
        br = launch(pw)
        ctx = br.new_context()

        if a.solution:
            tcfg = size_config("18x24")
            pwid, phei, M = 11.0, 8.5, 0.4
            best = None
            for (w, h) in ((8.5, 11.0), (11.0, 8.5)):
                cell = min((w - 2 * M) / an["cols"], (h - 2 * M - 0.9) / an["rows"])
                if best is None or cell > best[0]:
                    best = (cell, w, h)
            _, pwid, phei = best
            data = build_data(an, tcfg, pwid - 2 * M, phei - 2 * M, key=True, fill=fill_grey, title=a.title, byline=a.byline)
            data.update(title=a.title + ": The Solution", sw=0.6, outer=2.0, numRatio=0.3)
            htm = (SOLUTION_PAGE.replace("__FONTS__", font_faces()).replace("__PW__", str(pwid)).replace("__PH__", str(phei))
                   .replace("__M__", str(M)).replace("__CW__", str(pwid - 2 * M)).replace("__DATA__", _js_json(data)))
            hp = os.path.join(a.build_dir, "solution_letter.html")
            open(hp, "w", encoding="utf-8").write(htm)
            pg = ctx.new_page()
            pg.goto(Path(hp).resolve().as_uri())
            pg.wait_for_function("window.__done===true")
            info = pg.evaluate("window.__info")
            out = os.path.join(a.outroot, "solution_letter.pdf")
            os.makedirs(a.outroot, exist_ok=True)
            run_pdf(pg, pwid, phei, out)
            png_preview(out, out[:-4] + ".png", a.png_width)
            report["solution"] = dict(info, page=f"{pwid}x{phei}")
            print(json.dumps(report, indent=1) if not a.quiet else f"solution: {out}")
            br.close()
            return 0

        tw, th = parse_size(a.trim)
        tcfg = dict(size_config(a.trim), mode=a.mode)
        cw, ch = tw - 2 * tcfg["margin"], th - 2 * tcfg["margin"]
        outdir = os.path.join(a.outroot, a.trim.lower())
        os.makedirs(outdir, exist_ok=True)
        icons = pick_icons(an, spot_text=a.spot_text)
        make = {m.strip() for m in a.make.split(",")}

        def load(key, spot, bleed, fit=None, tag="x", fill=None, sw=None):
            data = build_data(an, tcfg, cw, ch, key=key, icons=icons if spot else None, fill=fill or fill_dark, title=a.title, byline=a.byline)
            if sw:
                data["sw"] = sw
            hp = os.path.join(a.build_dir, f"{a.trim}_{tag}.html")
            open(hp, "w", encoding="utf-8").write(build_poster_html(data, (tw, th), bleed, tcfg))
            pg = ctx.new_page()
            pg.goto(Path(hp).resolve().as_uri())
            pg.wait_for_function("window.__ready===true")
            return pg

        # 1. fit once (plain, no bleed: layout is bleed independent)
        pg = load(False, False, 0.0, tag="fit")
        fit = pg.evaluate("fitAll()")
        pg.close()
        if not fit.get("ok"):
            print("FIT FAILED", json.dumps(fit)[:2000])
            br.close()
            return 3
        fit_log = fit.pop("log")
        report["fit"] = fit
        report["fit_candidates"] = fit_log[:60]
        print("fit:", json.dumps(fit))

        def render(tag, key, spot, bleed, out_pdf, fill=None, sw=None):
            pg = load(key, spot, bleed, tag=tag, fill=fill, sw=sw)
            pg.evaluate("f=>{window.__plan=applyPlan(f);}", fit)
            ver = pg.evaluate("f=>verify(f)", fit)
            slack = pg.evaluate("window.__plan.slackInfo")
            return pg, ver, slack

        vers = {}
        for variant, spot, folder, fill in (("A", False, "A_black", fill_dark), ("B", True, "B_spot", fill_dark), ("C", False, "C_grey", fill_grey)):
            if variant not in make:
                continue
            sub = os.path.join(outdir, folder)
            os.makedirs(sub, exist_ok=True)
            pg, ver, slack = render(f"{variant}_bleed", False, spot, BLEED, None, fill)
            run_pdf(pg, tw + 2 * BLEED, th + 2 * BLEED, os.path.join(sub, "poster.pdf"))
            pg.close()
            png_preview(os.path.join(sub, "poster.pdf"), os.path.join(sub, "poster.png"), a.png_width)
            pg, ver2, slack = render(f"{variant}_trim", False, spot, 0.0, None, fill)
            run_pdf(pg, tw, th, os.path.join(sub, "poster_trim.pdf"))
            pg.close()
            vers[variant] = ver
            report.setdefault("slack", slack)
        if "key" in make:
            # scale the finished poster onto 11x17 (0.25 in unprintable margin); keep cell lines >= 0.55 pt after scaling
            sc = min((11 - 0.5) / tw, (17 - 0.5) / th)
            pg, ver, _ = render("key", True, False, 0.0, None, fill_grey, sw=max(tcfg["sw"], 0.55 / sc))
            pg.evaluate("""([s,tw,th])=>{const e=document.getElementById('sheet');
              e.style.transform='scale('+s+')';e.style.left=((11*96-tw*96*s)/2)+'px';e.style.top=((17*96-th*96*s)/2)+'px';
              document.getElementById('page').style.width='11in';document.getElementById('page').style.height='17in';}""", [sc, tw, th])
            pg.add_style_tag(content="@page{size:11in 17in;margin:0}html,body{width:11in!important;height:17in!important}")
            run_pdf(pg, 11, 17, os.path.join(outdir, "key.pdf"))
            pg.close()
        report["verify"] = vers
        json.dump(report, open(os.path.join(outdir, "fit.json"), "w"), indent=1)
        if not a.quiet:
            print(json.dumps(dict(fit=fit, verify=vers), indent=1))
        br.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
