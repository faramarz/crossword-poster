"""Classic crossword poster renderer (styles A, B, M): grid JSON -> vector PDFs (Playwright / Chromium).
The earlier renderer; `render` (render_news.py) is the main, newspaper-style one.

Styles: A "Classic Broadsheet" (cream paper, red accent), B "Courtside" (blue/orange sports-poster look),
M "Mono" (black on white).  Needs the Playfair Display / Source Serif 4 fonts for A and M, Bebas Neue / DM Sans for B:
run scripts/fetch_fonts.sh once.

Outputs (for --prefix P in --outdir D):
  P.pdf              trim + 0.125 in bleed on every side, vector, fonts embedded
  P_trim.pdf         exactly the trim size, no bleed
  P.png / P_trim.png low-DPI previews of the PDF itself
  P_key.pdf          answer key, 11 x 17 in (poster scaled, answers filled in)
  P_test11x17.pdf    test print, 11 x 17 in (poster scaled, blank grid)
  P_solution_letter.pdf   (--make solution_letter) letter-size filled grid, no clues

Usage:
  python -m crossword_poster render-classic out/grid.json --style M --outdir out/classic --title "My Crossword"
         [--make poster,trim,key,test,solution_letter] [--cell 0.8] [--trim 36x48] ...
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from pathlib import Path

from .common import BLEED, font_face, launch, png_preview, run_pdf

TRIM_W, TRIM_H = 24.0, 36.0
MARGIN = 0.75


# --------------------------------------------------------------- grid / clues
def load_csv_clues(path):
    m = {}
    if not path:
        return m
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a = re.sub(r"[^A-Z]", "", (row.get("grid") or row.get("grid_answer") or row.get("answer") or "").upper())
            c = (row.get("clue") or "").strip()
            if a and c and a not in m:
                m[a] = c
    return m


def analyse(gridjson, csv_clues):
    """Return dict(rows, cols, cells{(r,c)->letter}, nums{(r,c)->n}, entries[...], bbox, warnings)."""
    g = gridjson["grid"]
    R, C = len(g), len(g[0])
    cells = {(r, c): (g[r][c] or "").upper() for r in range(R) for c in range(C) if (g[r][c] or "").strip()}
    r0 = min(r for r, _ in cells); r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells); c1 = max(c for _, c in cells)
    has = lambda r, c: (r, c) in cells
    nums, entries, n = {}, [], 0
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
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
                        rr += dr; cc += dc
                    entries.append(dict(number=n, direction=d, answer=w, row=r, col=c))
    warns = []
    # clue lookup: explicit "clues" array > placements > csv
    ex_num = {(str(x["direction"]).lower(), int(x["number"])): x["clue"] for x in gridjson.get("clues", []) if "number" in x}
    ex_ans = {re.sub(r"[^A-Z]", "", str(x.get("answer", "")).upper()): x["clue"] for x in gridjson.get("clues", []) if x.get("answer")}
    pl = {}
    for p in gridjson.get("placements", []):
        if p.get("clue"):
            pl[(p["direction"], p["word"].upper())] = p["clue"]
        # sanity-check numbering against the generator's
        if (p["row"] - 0, p["col"]) in nums and nums[(p["row"], p["col"])] != p["number"]:
            warns.append(f"numbering differs from generator at {p['word']}")
    for e in entries:
        clue = ex_num.get((e["direction"], e["number"])) or ex_ans.get(e["answer"]) \
            or pl.get((e["direction"], e["answer"])) or csv_clues.get(e["answer"])
        if not clue:
            warns.append(f"NO CLUE for {e['number']} {e['direction']} {e['answer']}")
            clue = "(clue missing)"
        e["clue"] = re.sub(r"\s+", " ", str(clue)).strip()
        if len(e["clue"]) > 110:
            warns.append(f"long clue ({len(e['clue'])} chars) {e['number']} {e['direction']}: {e['clue'][:40]}...")
    return dict(r0=r0, c0=c0, rows=r1 - r0 + 1, cols=c1 - c0 + 1, cells=cells, nums=nums, entries=entries, warns=warns)


# --------------------------------------------------------------------- styles
def font_faces():
    """Static instances (made from the Google Fonts variable TTFs by scripts/fetch_fonts.sh) so Chromium embeds real TrueType, not Type 3."""
    return "\n".join([
        font_face("Playfair Display", "PlayfairDisplay", "PlayfairDisplay-Bold.ttf", 700),
        font_face("Playfair Display", "PlayfairDisplay", "PlayfairDisplay-Black.ttf", 900),
        font_face("Playfair Display", "PlayfairDisplay", "PlayfairDisplay-Italic.ttf", 400, "italic"),
        font_face("Playfair Display", "PlayfairDisplay", "PlayfairDisplay-BlackItalic.ttf", 900, "italic"),
        font_face("Source Serif 4", "SourceSerif4", "SourceSerif4-Regular.ttf", 400),
        font_face("Source Serif 4", "SourceSerif4", "SourceSerif4-SemiBold.ttf", 600),
        font_face("Source Serif 4", "SourceSerif4", "SourceSerif4-Bold.ttf", 700),
        font_face("Bebas Neue", "BebasNeue", "BebasNeue-Regular.ttf", 400),
        font_face("DM Sans", "DMSans", "DMSans-Regular.ttf", 400),
        font_face("DM Sans", "DMSans", "DMSans-Medium.ttf", 500),
        font_face("DM Sans", "DMSans", "DMSans-Bold.ttf", 700),
        font_face("DM Sans", "DMSans", "DMSans-ExtraBold.ttf", 800),
    ])


STYLE_A = dict(
    name="Classic Broadsheet",
    fonts=[("Playfair Display", "700"), ("Playfair Display", "900"), ("Playfair Display", "italic 400"), ("Playfair Display", "italic 900"), ("Source Serif 4", "400"), ("Source Serif 4", "600"), ("Source Serif 4", "700")],
    css="""
:root{--paper:#FBF7EE;--ink:#17140F;--accent:#A52A17;--muted:#5B5346;--cellfill:#FFFFFF;
 --clue-font:'Source Serif 4',serif;--num-font:'Source Serif 4',serif;--head-font:'Playfair Display',serif;--letter-font:'Source Serif 4',serif;}
.title{display:flex;flex-direction:column;align-items:stretch;}
.title .rt{height:4pt;background:var(--ink);} .title .rn{height:1pt;background:var(--ink);}
.title .dl{display:flex;justify-content:space-between;align-items:baseline;font:600 15pt/1 var(--clue-font);letter-spacing:.14em;text-transform:uppercase;padding:9pt 0 8pt;color:var(--ink);}
.title .dl span:nth-child(2){font-style:italic;text-transform:none;letter-spacing:.02em;font-weight:400;font-size:17pt;}
.title h1{font:900 140pt/.95 var(--head-font);letter-spacing:.015em;text-align:center;margin:12pt 0 0;color:var(--ink);white-space:nowrap;}
.title h1 em{font-style:italic;font-weight:900;color:var(--accent);letter-spacing:0;}
.title .sub{font:italic 400 36pt/1.1 var(--head-font);text-align:center;margin:4pt 0 12pt;color:var(--ink);}
.title .dbl{border-top:4pt solid var(--ink);border-bottom:1pt solid var(--ink);height:5pt;}
.hd{font:700 30pt/1 var(--head-font);letter-spacing:.16em;color:var(--ink);padding-bottom:7pt;border-bottom:2pt solid var(--accent);margin-bottom:11pt;display:flex;align-items:baseline;gap:.5em}
.hd small{font:italic 400 17pt/1 var(--clue-font);letter-spacing:.02em;color:var(--muted);}
.clue .n{font-weight:700;color:var(--accent);} .clue .len{color:var(--muted);white-space:nowrap}
#clues .blk+.blk{border-left:1pt solid var(--ink);padding-left:calc(.5in*var(--gs,1));margin-left:calc(.5in*var(--gs,1));}
.foot{font:600 14pt/1 var(--clue-font);letter-spacing:.16em;text-transform:uppercase;text-align:center;padding-top:10pt;border-top:1pt solid var(--ink);color:var(--ink);}
.foot b{color:var(--accent)}
""",
    title_html="""<!--TOP--><div class="rt"></div><div class="dl"><span>{est}</span><span>{kicker}</span><span>{edition}</span></div><div class="rn"></div><!--/TOP-->
<h1>{title_html}</h1><p class="sub">{subtitle}</p><div class="dbl"></div>""",
    cell_stroke=1.75, num_pt=10, grid_gap=0.3, clue_gap=0.4,
    cell_text="#17140F", key_color="#A52A17",
)

_ARCS = "".join(f'<circle cx="2050" cy="330" r="{r}" fill="none" stroke="rgba(255,246,229,.16)" stroke-width="3"/>' for r in range(110, 1500, 90))
_DOTS = ('<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="13" cy="13" r="2.2" fill="rgba(255,246,229,.13)"/></pattern>')

STYLE_B = dict(
    name="Courtside",
    fonts=[("Bebas Neue", "400"), ("DM Sans", "400"), ("DM Sans", "500"), ("DM Sans", "700"), ("DM Sans", "800")],
    css="""
:root{--paper:#FFF6E5;--ink:#0F1B4D;--accent:#C4410C;--muted:#4A4F6E;--cellfill:#FFFFFF;--blue:#1B3A9E;--orange:#F26B21;--yellow:#FFC93C;
 --clue-font:'DM Sans',sans-serif;--num-font:'DM Sans',sans-serif;--head-font:'Bebas Neue',sans-serif;--letter-font:'DM Sans',sans-serif;}
.title{position:relative;display:flex;flex-direction:column;align-items:flex-start;padding-bottom:6pt;}
.title .tbg{position:absolute;z-index:-1;left:calc(-1*(var(--m) + var(--bleed)));right:calc(-1*(var(--m) + var(--bleed)));top:calc(-1*(var(--m) + var(--bleed)));bottom:-22pt;background:var(--blue);overflow:hidden;}
.title .tbg svg{position:absolute;right:0;top:0;width:100%;height:100%}
.title .tbg .st{position:absolute;left:0;right:0;bottom:0;height:22pt;background:linear-gradient(to bottom,var(--orange) 0 8pt,var(--yellow) 8pt 15pt,var(--paper) 15pt 22pt);}
.title .kick{font:700 17pt/1 var(--clue-font);letter-spacing:.3em;color:var(--yellow);text-transform:uppercase;margin-top:6pt}
.title h1{font:400 190pt/.84 var(--head-font);letter-spacing:.01em;margin:12pt 0 0;color:var(--paper);white-space:nowrap;}
.title h1 em{font-style:normal;color:var(--yellow);}
.title .sub{font:700 31pt/1.1 var(--clue-font);letter-spacing:.17em;text-transform:uppercase;color:var(--paper);margin:14pt 0 6pt;}
.hd{display:inline-flex;align-self:flex-start;align-items:baseline;gap:.6em;font:400 44pt/1 var(--head-font);letter-spacing:.12em;color:var(--paper);background:var(--ink);padding:4pt 18pt 2pt;margin-bottom:11pt;border-radius:3pt;}
.hd small{font:500 15pt/1 var(--clue-font);letter-spacing:.04em;color:var(--yellow);}
.clue .n{font-weight:800;color:var(--accent);} .clue .len{color:var(--muted);white-space:nowrap}
#clues .blk+.blk{border-left:2pt solid var(--orange);padding-left:calc(.5in*var(--gs,1));margin-left:calc(.5in*var(--gs,1));}
.foot{font:700 14pt/1 var(--clue-font);letter-spacing:.2em;text-transform:uppercase;text-align:center;padding-top:10pt;color:var(--ink);display:flex;align-items:center;gap:18pt;}
.foot:before,.foot:after{content:'';flex:1;height:7pt;background:linear-gradient(to bottom,var(--orange) 0 2.5pt,transparent 2.5pt 4.5pt,var(--yellow) 4.5pt 7pt);}
""",
    title_html="""<div class="tbg"><svg viewBox="0 0 2200 700" preserveAspectRatio="xMaxYMin slice"><defs>__DOTS__</defs><rect width="2200" height="700" fill="url(#dots)"/>__ARCS__</svg><div class="st"></div></div>
{kick_html}<h1>{title_html}</h1><p class="sub">{subtitle}</p>""".replace("__DOTS__", _DOTS).replace("__ARCS__", _ARCS),
    cell_stroke=2.0, num_pt=10, grid_gap=0.5, clue_gap=0.4,
    cell_text="#0F1B4D", key_color="#C4410C",
)


STYLE_M = dict(
    name="Mono (black on white)", mono=True,
    fonts=[("Playfair Display", "900"), ("Source Serif 4", "400"), ("Source Serif 4", "600"), ("Source Serif 4", "700")],
    css="""
:root{--paper:#FFFFFF;--ink:#000000;--accent:#000000;--muted:#333333;--cellfill:#FFFFFF;
 --clue-font:'Source Serif 4',serif;--num-font:'Source Serif 4',serif;--head-font:'Playfair Display',serif;--letter-font:'Source Serif 4',serif;}
.title{display:flex;flex-direction:column;align-items:stretch;}
.title h1{font:900 100pt/1.02 var(--head-font);text-align:center;margin:0;color:#000;white-space:nowrap;}
.title .sub{font:600 26pt/1.1 var(--clue-font);letter-spacing:.03em;text-align:center;margin:.35em 0 .45em;color:#000;}
.title .dbl{border-top:3pt solid #000;border-bottom:1pt solid #000;height:5pt;}
.hd{font:700 30pt/1 var(--clue-font);letter-spacing:.16em;color:#000;padding-bottom:7pt;border-bottom:2pt solid #000;margin-bottom:11pt;display:flex;align-items:baseline;gap:.5em}
.hd small{font:600 17pt/1 var(--clue-font);letter-spacing:.02em;color:var(--muted);}
.clue .n{font-weight:700;color:#000;} .clue .len{color:var(--muted);white-space:nowrap}
#clues .blk+.blk{border-left:1.25pt solid #000;padding-left:calc(.5in*var(--gs,1));margin-left:calc(.5in*var(--gs,1));}
.foot{font:700 14pt/1 var(--clue-font);letter-spacing:.16em;text-transform:uppercase;text-align:center;padding-top:10pt;border-top:1pt solid #000;color:#000;}
""",
    title_html="""<h1>{title_html}</h1><p class="sub">{subtitle}</p><div class="dbl"></div>""",
    cell_stroke=1.0, num_pt=10, grid_gap=0.3, clue_gap=0.4,
    cell_text="#000000", key_color="#000000",
)

STYLES = {"M": STYLE_M, "MONO": STYLE_M, "A": STYLE_A, "BROADSHEET": STYLE_A, "B": STYLE_B, "COURTSIDE": STYLE_B}

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>poster</title><style>
__FONTS__
@page{size:__PW__in __PH__in;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:__PW__in;height:__PH__in;overflow:hidden;background:__PAPER__;-webkit-print-color-adjust:exact;print-color-adjust:exact}
:root{--bleed:__BLEED__in;--m:__MARGIN__in;--gs:__GS__}
.hd{zoom:__HZ__}
__STYLE_CSS__
#sheet{isolation:isolate;position:absolute;left:0;top:0;width:__SW__in;height:__SH__in;background:var(--paper);overflow:hidden;transform-origin:0 0;}
#poster{position:absolute;left:var(--bleed);top:var(--bleed);width:__TW__in;height:__TH__in;}
#inner{position:absolute;left:var(--m);top:var(--m);right:var(--m);bottom:var(--m);display:flex;flex-direction:column;color:var(--ink);font-family:var(--clue-font)}
header.title,.foot{flex:none}
header.title,.foot{zoom:__TZ__}
#gridwrap{display:flex;justify-content:center;flex:none}
#gridwrap svg{display:block;overflow:visible}
#clues{flex:1;min-height:0;display:flex;}
.blk{display:flex;flex-direction:column;min-width:0;min-height:0}
.cols{flex:1;min-height:0;column-fill:balance;column-gap:calc(.4in*var(--gs,1));}
.clue{display:grid;grid-template-columns:1.9em 1fr;break-inside:avoid;margin-bottom:.32em;line-height:1.2;font-family:var(--clue-font);}
.clue .n{font-family:var(--num-font);}
.clue .t{hyphens:manual;overflow-wrap:break-word;min-width:0}
.foot{margin-top:.14in}
.foot.nofoot{height:0;min-height:0;margin:0;padding:0;border:0;overflow:hidden}
.foot.nofoot:before,.foot.nofoot:after{display:none}
#page{position:absolute;left:0;top:0;width:__PW__in;height:__PH__in;overflow:hidden;clip-path:inset(0)}
</style></head><body><div id="page"><div id="sheet"><div id="poster"><div id="inner">
<header class="title">__TITLE__</header>
<div id="gridwrap"></div>
<div id="clues"></div>
<footer class="foot__NOFOOT__">__FOOT__</footer>
</div></div></div></div>
<script>
const D=__DATA__;
const NS='http://www.w3.org/2000/svg';
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function buildGrid(cellIn){
  const cpt=cellIn*72,W=D.cols*cpt,H=D.rows*cpt;let sw=D.stroke,outer=0;
  if(D.mono){if(!D.sfix)sw=Math.min(1.0,Math.max(0.75,cpt*0.04));outer=Math.max(1.0,sw+0.5);}
  const pad=Math.max(sw,outer);
  const gw=document.getElementById('gridwrap');gw.innerHTML='';
  const svg=document.createElementNS(NS,'svg');
  svg.setAttribute('width',(W+2*pad)+'pt');svg.setAttribute('height',(H+2*pad)+'pt');
  svg.setAttribute('viewBox',`${-pad} ${-pad} ${W+2*pad} ${H+2*pad}`);
  let s='';
  for(const c of D.cells){
    const x=c.c*cpt,y=c.r*cpt;
    s+=`<rect x="${x}" y="${y}" width="${cpt}" height="${cpt}" fill="${D.cellfill}" stroke="${D.ink}" stroke-width="${sw}" stroke-linejoin="miter"/>`;
  }
  if(outer){
    const st=new Set(D.cells.map(c=>c.r+','+c.c));let p='';
    for(const c of D.cells){const x=c.c*cpt,y=c.r*cpt;
      if(!st.has((c.r-1)+','+c.c)) p+=`M${x} ${y}H${x+cpt}`;
      if(!st.has((c.r+1)+','+c.c)) p+=`M${x} ${y+cpt}H${x+cpt}`;
      if(!st.has(c.r+','+(c.c-1))) p+=`M${x} ${y}V${y+cpt}`;
      if(!st.has(c.r+','+(c.c+1))) p+=`M${x+cpt} ${y}V${y+cpt}`;}
    s+=`<path d="${p}" fill="none" stroke="${D.ink}" stroke-width="${outer}" stroke-linecap="square"/>`;
  }
  for(const c of D.cells){
    const x=c.c*cpt,y=c.r*cpt;
    if(c.n) s+=`<text x="${x+0.4*D.numpt}" y="${y+1.25*D.numpt}" font-family="${D.numfont}" font-weight="700" font-size="${D.numpt}" fill="${D.ink}">${c.n}</text>`;
    if(D.key) s+=`<text x="${x+cpt/2}" y="${y+cpt*0.76}" text-anchor="middle" font-family="${D.letterfont}" font-weight="700" font-size="${cpt*0.56}" fill="${D.keycolor}">${c.l}</text>`;
  }
  svg.innerHTML=s;gw.appendChild(svg);
  gw.style.marginTop=D.gridgap+'in';gw.style.marginBottom=D.cluegap+'in';
}
function li(e){return `<div class="clue"><span class="n">${e.number}</span><span class="t">${esc(e.clue)}${(D.lengths && !/\(\d+(,\d+)+\)\s*$/.test(e.clue))?` <span class="len">(${e.answer.length})</span>`:''}</span></div>`;}
function buildClues(fs,ca){
  const cl=document.getElementById('clues');cl.style.fontSize=fs+'pt';
  const A=D.entries.filter(e=>e.direction==='across'),Dn=D.entries.filter(e=>e.direction==='down');
  const cd=(D.tc||4)-ca;
  const blk=(title,list,n)=>`<div class="blk" style="flex:${n} 1 0"><div class="hd">${title}<small>${list.length} clues</small></div><div class="cols" style="column-count:${n}">${list.map(li).join('')}</div></div>`;
  cl.innerHTML=blk('ACROSS',A,ca)+blk('DOWN',Dn,cd);
}
function fitTitle(){
  if(!D.titlept) return;
  const h=document.querySelector('.title h1'); if(!h) return;
  let pt=D.titlept; h.style.fontSize=pt+'pt';
  while(h.scrollWidth>h.clientWidth+0.5&&pt>12){pt-=0.5;h.style.fontSize=pt+'pt';}
  const sb=document.querySelector('.title .sub'); if(sb) sb.style.fontSize=(pt*D.subratio)+'pt';
  D.titlefit=pt;
}
function overflow(){
  for(const c of document.querySelectorAll('.cols')){
    const r=c.getBoundingClientRect();
    if(c.scrollWidth>c.clientWidth+1) return true;
    for(const k of c.children){const q=k.getBoundingClientRect();
      if(q.bottom>r.bottom+1||q.right>r.right+1||q.left<r.left-1) return true;}
  }
  const inner=document.getElementById('inner').getBoundingClientRect(),ft=document.querySelector('.foot').getBoundingClientRect();
  if(ft.bottom>inner.bottom+1||ft.top<document.getElementById('clues').getBoundingClientRect().bottom-1) return true;
  return false;
}
function fitAll(o){
  fitTitle();
  const nA=D.entries.filter(e=>e.direction==='across').reduce((s,e)=>s+e.clue.length+8,0);
  const nD=D.entries.filter(e=>e.direction==='down').reduce((s,e)=>s+e.clue.length+8,0);
  const f=nA/(nA+nD);const T=D.tc||4;let pref,cas;
  if(T===4){pref=f<0.3?1:(f>0.7?3:2);cas=[pref,...[2,1,3].filter(x=>x!==pref)];}
  else{pref=Math.max(1,Math.min(T-1,Math.round(f*T)));cas=[pref,...Array.from({length:T-1},(_,i)=>i+1).filter(x=>x!==pref).sort((a,b)=>Math.abs(a-f*T)-Math.abs(b-f*T))];}
  for(let fs=o.fsMax;fs>=o.fsMin-1e-6;fs-=0.5){
    for(let cell=o.cell;cell>=o.cellMin-1e-6;cell-=0.025){
      for(const ca of cas){
        buildGrid(cell);buildClues(fs,ca);
        if(!overflow()) return {ok:true,fs,cell:Math.round(cell*1000)/1000,ca};
      }}}
  buildGrid(o.cellMin);buildClues(o.fsMin,pref);
  return {ok:false,fs:o.fsMin,cell:o.cellMin,ca:pref};
}
function applyFit(f){fitTitle();buildGrid(f.cell);buildClues(f.fs,f.ca);return !overflow();}
function metrics(){
  const r=e=>e.getBoundingClientRect();
  const k=r(document.querySelector('.title')),g=r(document.querySelector('#gridwrap svg')),c=r(document.getElementById('clues'));
  return {titleH:k.height/96,gridW:g.width/96,gridH:g.height/96,cluesH:c.height/96};
}
</script></body></html>"""


def build_html(style, an, cfg, fit=None):
    S = STYLES[style.upper()]
    key = cfg["key"]
    cells = []
    for (r, c), l in sorted(an["cells"].items()):
        cells.append(dict(r=r - an["r0"], c=c - an["c0"], l=l, n=an["nums"].get((r, c), 0)))
    data = dict(
        rows=an["rows"], cols=an["cols"], cells=cells,
        entries=sorted(an["entries"], key=lambda e: e["number"]),
        stroke=cfg.get("stroke") or S["cell_stroke"], numpt=cfg.get("num_pt") or S["num_pt"], tc=cfg.get("clue_cols", 4), mono=bool(S.get("mono")), sfix=cfg.get("stroke") is not None,
        titlept=(cfg.get("title_pt") if S.get("mono") else None), subratio=0.27, ink=S["cell_text"], cellfill="#FFFFFF",
        numfont="DM Sans" if S is STYLE_B else "Source Serif 4",
        letterfont="DM Sans" if S is STYLE_B else "Source Serif 4",
        keycolor=S["key_color"], key=key, lengths=cfg["lengths"],
        gridgap=S["grid_gap"] * cfg.get("gap_scale", 1.0), cluegap=S["clue_gap"] * cfg.get("gap_scale", 1.0),
    )
    t = cfg["title"].strip()
    parts = t.upper().rsplit(" ", 1)
    title_html = (html.escape(parts[0]) + " <em>" + html.escape(parts[1]) + "</em>") if len(parts) == 2 else html.escape(t.upper())
    if S.get("mono"):
        if cfg.get("title_lines", 1) == 2:
            wd = t.split(" "); k = min(range(1, len(wd)), key=lambda i: abs(len(" ".join(wd[:i])) - len(" ".join(wd[i:]))))
            title_html = html.escape(" ".join(wd[:k])) + "<br>" + html.escape(" ".join(wd[k:]))
        else:
            title_html = html.escape(t)
    kparts = [html.escape(x) for x in (cfg["est"], cfg["edition"]) if x]
    kick_html = '<div class="kick">' + " &nbsp;·&nbsp; ".join(kparts) + "</div>" if kparts else ""
    th = S["title_html"].format(est=html.escape(cfg["est"]), kicker=html.escape(cfg["kicker"]), edition=html.escape(cfg["edition"]),
                                title_html=title_html, subtitle=html.escape(cfg["subtitle"]), kick_html=kick_html)
    if cfg.get("no_topline"):
        th = re.sub(r"<!--TOP-->.*?<!--/TOP-->", "", th, flags=re.S)
    foot = html.escape(cfg["footer"])
    if key:
        foot = "Answer key &nbsp;·&nbsp; " + foot
    if cfg.get("no_footer"):
        foot = ""
    bleed = cfg["bleed"]
    pw, ph = cfg["page"]
    tw, th_ = cfg.get("trim", (TRIM_W, TRIM_H))
    tz = 1.0 if STYLES[style.upper()].get("mono") else cfg.get("title_scale", 1.0)
    sw, sh = tw + 2 * bleed, th_ + 2 * bleed
    paper = "#FFFFFF" if S is STYLE_M else ("#FBF7EE" if S is STYLE_A else "#FFF6E5")
    page = (PAGE.replace("__FONTS__", font_faces()).replace("__PW__", str(pw)).replace("__PH__", str(ph))
            .replace("__PAPER__", paper)
            .replace("__TW__", str(tw)).replace("__TH__", str(th_)).replace("__TZ__", str(tz))
            .replace("__BLEED__", str(bleed)).replace("__MARGIN__", str(cfg.get("margin", MARGIN))).replace("__GS__", str(cfg.get("gap_scale", 1.0))).replace("__HZ__", str(cfg.get("hd_scale", 1.0)))
            .replace("__SW__", str(sw)).replace("__SH__", str(sh))
            .replace("__STYLE_CSS__", S["css"]).replace("__TITLE__", th).replace("__FOOT__", foot).replace("__NOFOOT__", " nofoot" if cfg.get("no_footer") else "")
            .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))
    return page



def build_solution_html(style, an, cfg):
    """Letter-size 'last week's solution' page: filled grid, small numbers, title + footer, no clues. Returns (html, orient, cell_in)."""
    S = STYLES[style.upper()]
    rows, cols = an["rows"], an["cols"]
    M, HEAD, FOOT = 0.35, 0.85, (0.0 if cfg.get("no_footer") else 0.4)
    mono = bool(S.get("mono"))
    if mono: HEAD = 1.05
    best = None
    for orient, (pw, ph) in (("portrait", (8.5, 11.0)), ("landscape", (11.0, 8.5))):
        cell = min((pw - 2 * M) / cols, (ph - 2 * M - HEAD - FOOT) / rows)
        if best is None or cell > best[0]:
            best = (cell, orient, pw, ph)
    cell, orient, pw, ph = best
    cell = int(cell * 1000) / 1000.0
    cpt = cell * 72
    W, H = cols * cpt, rows * cpt
    sw = 0.75
    outer = 0
    if mono:
        sw = round(min(1.0, max(0.75, cpt * 0.04)), 2); outer = max(1.0, sw + 0.5)
    numpt = max(4.0, round(cpt * 0.27, 2))
    letpt = round(cpt * 0.62, 2)
    nf = "'DM Sans'" if S is STYLE_B else "'Source Serif 4'"
    parts = []
    for (r, c), l in sorted(an["cells"].items()):
        x, y = (c - an["c0"]) * cpt, (r - an["r0"]) * cpt
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cpt:.2f}" height="{cpt:.2f}" fill="#FFFFFF" stroke="{S["cell_text"]}" stroke-width="{sw}"/>')
    for (r, c), l in sorted(an["cells"].items()):
        x, y = (c - an["c0"]) * cpt, (r - an["r0"]) * cpt
        n = an["nums"].get((r, c))
        if n:
            parts.append(f'<text x="{x + 1.2:.2f}" y="{y + numpt + 0.6:.2f}" font-family="{nf}" font-weight="700" font-size="{numpt}" fill="{S["cell_text"]}">{n}</text>')
        parts.append(f'<text x="{x + cpt / 2:.2f}" y="{y + cpt * 0.80:.2f}" text-anchor="middle" font-family="{nf}" font-weight="700" font-size="{letpt}" fill="{S["key_color"]}">{l}</text>')
    pad = max(sw, outer)
    if outer:
        cs = set(an["cells"]); d = ""
        for (r, c) in cs:
            x, y = (c - an["c0"]) * cpt, (r - an["r0"]) * cpt
            if (r - 1, c) not in cs: d += f"M{x:.2f} {y:.2f}H{x + cpt:.2f}"
            if (r + 1, c) not in cs: d += f"M{x:.2f} {y + cpt:.2f}H{x + cpt:.2f}"
            if (r, c - 1) not in cs: d += f"M{x:.2f} {y:.2f}V{y + cpt:.2f}"
            if (r, c + 1) not in cs: d += f"M{x + cpt:.2f} {y:.2f}V{y + cpt:.2f}"
        parts.insert(len(cs), f'<path d="{d}" fill="none" stroke="{S["cell_text"]}" stroke-width="{outer}" stroke-linecap="square"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W + 2 * pad}pt" height="{H + 2 * pad}pt" viewBox="{-pad} {-pad} {W + 2 * pad} {H + 2 * pad}">'
           + "".join(parts) + "</svg>")
    t = cfg["title"].strip()
    title = html.escape(t) + ": The Solution"
    if mono:
        a_, b_ = t, "The Solution"
        title = html.escape(a_) + ":<br>" + html.escape(b_)
    foot = html.escape(cfg["footer"])
    ftdiv = "" if cfg.get("no_footer") else f"<div class='ft'>{foot}</div>"
    toprules = "" if (cfg.get("no_topline") or mono) else "<div class='rt'></div><div class='rn'></div>"
    h1attr = " data-fit='34'" if mono else ""
    h1css = "h1[data-fit]{white-space:nowrap}.sol-rule{align-self:stretch;height:3pt;background:#000;margin-top:6pt;border-bottom:1pt solid #000;padding-bottom:0}" if mono else ""
    page = ("<!doctype html><html><head><meta charset='utf-8'><title>solution</title><style>"
            + font_faces() + f"@page{{size:{pw}in {ph}in;margin:0}}"
            "*{box-sizing:border-box;margin:0;padding:0}"
            f"html,body{{width:{pw}in;height:{ph}in;background:var(--paper);-webkit-print-color-adjust:exact;print-color-adjust:exact}}"
            + S["css"].split("\n.title")[0] +
            f"#s{{position:absolute;left:{M}in;top:{M}in;right:{M}in;bottom:{M}in;display:flex;flex-direction:column;align-items:center;color:var(--ink)}}"
            ".rt{align-self:stretch;height:3pt;background:var(--ink)} .rn{align-self:stretch;height:1pt;background:var(--ink);margin-top:2pt}"
            "h1{font:900 30pt/1.05 var(--head-font);text-align:center;margin-top:7pt;letter-spacing:.01em;color:var(--ink)}"
            "h1 em{font-style:italic;color:var(--accent)}"
            ".gw{flex:1;display:flex;align-items:center;justify-content:center;width:100%}"
            ".ft{align-self:stretch;border-top:1pt solid var(--ink);padding-top:6pt;text-align:center;font:600 9pt/1 var(--clue-font);letter-spacing:.16em;text-transform:uppercase}"
            + h1css +
            "</style></head><body><div id='s'>" + toprules +
            f"<h1{h1attr}>{title}</h1>" + ("<div class='sol-rule'></div>" if mono else "") + f"<div class='gw'>{svg}</div>{ftdiv}</div>"
            "<script>document.fonts.ready.then(()=>{const h=document.querySelector('h1[data-fit]');if(h){let pt=+h.dataset.fit;h.style.fontSize=pt+'pt';while(h.scrollWidth>h.clientWidth+0.5&&pt>10){pt-=0.5;h.style.fontSize=pt+'pt';}}window.__done=true;});</script>"
            "</body></html>")
    return page, orient, cell, (pw, ph)

def main(argv=None):
    ap = argparse.ArgumentParser(prog="crossword_poster render-classic", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("grid", help="grid JSON (generate format; optional top-level 'clues' array)")
    ap.add_argument("--style", default="A", help="A (Classic Broadsheet), B (Courtside) or M (Mono black on white)")
    ap.add_argument("--csv", default=None, help="CSV with a grid/answer column + a clue column (fallback clue source)")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--prefix", default=None, help="output stem; default <grid stem>_style<X>")
    ap.add_argument("--make", default="poster,trim,key,test", help="comma list of poster,trim,key,test,solution_letter (solution_letter is opt-in: letter-size filled grid, no clues)")
    ap.add_argument("--key-out", default=None, help="override key PDF path")
    ap.add_argument("--test-out", default=None, help="override test-print PDF path")
    ap.add_argument("--cell", type=float, default=0.8, help="preferred box size in inches (auto-shrinks to --cell-min)")
    ap.add_argument("--cell-min", type=float, default=0.75)
    ap.add_argument("--font", type=float, default=20.0, help="preferred clue size, pt")
    ap.add_argument("--font-min", type=float, default=16.0)
    ap.add_argument("--no-lengths", action="store_true", help="omit the (n) letter counts after clues")
    ap.add_argument("--title", default="My Crossword")
    ap.add_argument("--subtitle", default="A custom crossword poster")
    ap.add_argument("--kicker", default="", help="small line above the title (styles A, B); empty = none")
    ap.add_argument("--est", default="", help="left word of the top line, e.g. 'Est. 2000' (styles A, B); empty = none")
    ap.add_argument("--edition", default="", help="right word of the top line, e.g. 'First Edition' (styles A, B); empty = none")
    ap.add_argument("--footer", default="", help="footer line; empty = no footer")
    ap.add_argument("--build-dir", default=None, help="scratch HTML directory (default OUTDIR/.build)")
    ap.add_argument("--png-width", type=int, default=1200)
    ap.add_argument("--solution-out", default=None, help="override solution_letter PDF path (used by --make solution_letter)")
    ap.add_argument("--no-topline", action="store_true", help="drop the EST./kicker/edition line and its rules (styles A and M)")
    ap.add_argument("--no-footer", action="store_true", help="drop the footer line (and its rule) on every output")
    ap.add_argument("--title-lines", type=int, default=1, choices=(1, 2), help="style M only: title on 1 or 2 balanced lines")
    ap.add_argument("--title-pt", type=float, default=None, help="style M only: maximum title size in pt (auto-shrinks to fit the width); default 150 x trim width / 24")
    ap.add_argument("--clue-cols", type=int, default=4, help="total clue columns across the Across+Down blocks (default 4; use 6 on large trims)")
    ap.add_argument("--gap-scale", type=float, default=1.0, help="scales clue column gaps and grid/clue spacing (default 1)")
    ap.add_argument("--hd-scale", type=float, default=1.0, help="zoom for the ACROSS/DOWN headings (default 1)")
    ap.add_argument("--margin", type=float, default=MARGIN, help="inner page margin in inches (default 0.75)")
    ap.add_argument("--num-pt", type=float, default=None, help="clue-number size inside boxes, pt (default from style: 10)")
    ap.add_argument("--stroke", type=float, default=None, help="box outline width, pt (default from style)")
    ap.add_argument("--trim", default="24x36", help="trim size in inches, WxH (default 24x36; use 36x48 for the large format; bleed stays 0.125 in)")
    ap.add_argument("--title-scale", type=float, default=None, help="zoom for title block and footer (default: trim width / 24)")
    a = ap.parse_args(argv)
    if not (a.est or a.kicker or a.edition):
        a.no_topline = True
    if not a.footer:
        a.no_footer = True

    from playwright.sync_api import sync_playwright

    gj = json.load(open(a.grid))
    an = analyse(gj, load_csv_clues(a.csv))
    for w in an["warns"]:
        print("WARN", w, file=sys.stderr)
    tw_, th2_ = (float(x) for x in a.trim.lower().split("x"))
    tz_ = a.title_scale if a.title_scale else tw_ / 24.0
    scale_small = min((11 - 0.5) / tw_, (17 - 0.5) / th2_)
    S = STYLES[a.style.upper()]
    letter = "M" if S is STYLE_M else ("A" if S is STYLE_A else "B")
    prefix = a.prefix or f"{os.path.splitext(os.path.basename(a.grid))[0]}_style{letter}"
    os.makedirs(a.outdir, exist_ok=True)
    P = lambda s: os.path.join(a.outdir, prefix + s)
    make = {m.strip() for m in a.make.split(",")}
    build_dir = a.build_dir or os.path.join(a.outdir, ".build")
    os.makedirs(build_dir, exist_ok=True)
    base = dict(trim=(tw_, th2_), title_scale=tz_, no_topline=a.no_topline, no_footer=a.no_footer, title_lines=a.title_lines, title_pt=(a.title_pt or 150.0 * tw_ / 24.0), clue_cols=a.clue_cols, gap_scale=a.gap_scale, hd_scale=a.hd_scale, margin=a.margin, num_pt=a.num_pt, stroke=a.stroke, title=a.title, subtitle=a.subtitle, kicker=a.kicker, est=a.est, edition=a.edition,
                footer=a.footer, lengths=not a.no_lengths)
    report = dict(trim=f"{tw_:g}x{th2_:g}", title_scale=tz_, style=S["name"], entries=len(an["entries"]), grid=f"{an['cols']}x{an['rows']}", pdfs={})

    with sync_playwright() as pw:
        br = launch(pw)
        ctx = br.new_context()
        fit = {}

        def load(cfg, tag):
            cfgx = dict(base, **cfg)
            hp = os.path.join(build_dir, f"{prefix}_{tag}.html")
            open(hp, "w", encoding="utf-8").write(build_html(a.style, an, cfgx))
            pg = ctx.new_page()
            pg.goto(Path(hp).resolve().as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_function("document.fonts.status==='loaded'")
            missing = pg.evaluate("async fams=>{await Promise.all(fams.map(f=>document.fonts.load(f)));return fams.filter(f=>!document.fonts.check(f));}",
                                  [f"{w} 20px '{fam}'" for fam, w in S["fonts"]])
            loaded = pg.evaluate("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family+' '+f.weight+' '+f.style)")
            if missing:
                print("WARN fonts failed to load:", missing, file=sys.stderr)
            report.setdefault("fonts_loaded", sorted(set(loaded)))
            return pg

        def fit_page(pg):
            if "f" not in fit:
                fit["f"] = pg.evaluate("o=>fitAll(o)", dict(fsMax=a.font, fsMin=a.font_min, cell=a.cell, cellMin=a.cell_min))
            ok = pg.evaluate("f=>applyFit(f)", fit["f"])
            return fit["f"], ok

        def finish_scaled(pg, out, scale):
            pg.evaluate("""s=>{const e=document.getElementById('sheet');
              e.style.transform='scale('+s+')';e.style.left=((11*96-TW*96*s)/2)+'px';e.style.top=((17*96-TH*96*s)/2)+'px';}""".replace("TW", str(tw_)).replace("TH", str(th2_)), scale)
            run_pdf(pg, 11, 17, out)
            pg.close()

        if "poster" in make or "trim" in make:
            for tag, bl, out in (("poster", BLEED, P(".pdf")), ("trim", 0, P("_trim.pdf"))):
                if tag not in make:
                    continue
                pg = load(dict(key=False, bleed=bl, scale=1, page=(tw_ + 2 * bl, th2_ + 2 * bl)), tag)
                f, ok = fit_page(pg)
                if tag == "poster":
                    report["fit"] = dict(f, overflow_free=ok, **pg.evaluate("metrics()"))
                run_pdf(pg, tw_ + 2 * bl, th2_ + 2 * bl, out)
                pg.close()
                report["pdfs"][tag] = out
                png_preview(out, out[:-4] + ".png", a.png_width)
        for tag, out in (("key", a.key_out or P("_key.pdf")), ("test", a.test_out or P("_test11x17.pdf"))):
            if tag not in make:
                continue
            pg = load(dict(key=(tag == "key"), bleed=0, scale=scale_small, page=(11, 17)), tag)
            f, ok = fit_page(pg)
            finish_scaled(pg, out, scale_small)
            report["pdfs"][tag] = out
        if "solution_letter" in make:
            sp = a.solution_out or P("_solution_letter.pdf")
            shtml, orient, scell, (spw, sph) = build_solution_html(a.style, an, dict(base))
            hp = os.path.join(build_dir, f"{prefix}_solution_letter.html")
            open(hp, "w", encoding="utf-8").write(shtml)
            pg = ctx.new_page()
            pg.goto(Path(hp).resolve().as_uri())
            pg.wait_for_function("document.fonts.status==='loaded'")
            pg.evaluate("async fams=>{await Promise.all(fams.map(f=>document.fonts.load(f)));}", [f"{w} 20px '{fam}'" for fam, w in S["fonts"]])
            pg.wait_for_function("window.__done===true")
            run_pdf(pg, spw, sph, sp)
            pg.close()
            png_preview(sp, sp[:-4] + ".png", a.png_width)
            report["pdfs"]["solution_letter"] = sp
            report["solution_letter"] = dict(orientation=orient, box_in=scell, page=f"{spw}x{sph}")
        br.close()
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
