#!/usr/bin/env python3
"""generate.py 의 단계 데이터로 단독 실행 가능한 HTML 뷰어를 만든다.

실행: python3 generate_html.py  ->  pod-creation-flow.html
"""
import json
import os

from generate import STEPS, Page

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pod-creation-flow.html")

# 다이어그램 영역 (draw.io 좌표계 기준) — 제목·탭·설명은 HTML 로 따로 그린다
VX, VY, VW, VH = 20, 85, 1560, 665
SKIP = ("title", "desc", "hint")


def style_dict(s):
    return dict(kv.split("=", 1) for kv in s.split(";") if "=" in kv)


def vertex_css(c):
    """draw.io vertex 스타일을 CSS 로 변환 (위치 제외)."""
    raw = c.get("style", "")
    st = style_dict(raw)
    g = c.find("mxGeometry")
    w, h = float(g.get("width")), float(g.get("height"))
    css = {}
    is_text = raw.startswith("text;")
    if not is_text:
        fill = st.get("fillColor", "none")
        stroke = st.get("strokeColor", "none")
        sw = float(st.get("strokeWidth", "1"))
        css["background"] = "transparent" if fill == "none" else fill
        css["border"] = (f"{sw}px {'dashed' if st.get('dashed') == '1' else 'solid'} "
                         f"{'transparent' if stroke == 'none' else stroke}")
        if st.get("rounded") == "1":
            css["border-radius"] = f"{min(w, h) * float(st.get('arcSize', '15')) / 100:.0f}px"
        css["box-shadow"] = "0 4px 14px rgba(232,89,12,.35)" if st.get("shadow") == "1" else "none"
    css["font-size"] = st.get("fontSize", "12") + "px"
    css["color"] = st.get("fontColor", "#212529")
    css["font-weight"] = "700" if st.get("fontStyle") == "1" else "400"
    css["text-align"] = st.get("align", "center")
    css["justify-content"] = {"left": "flex-start", "right": "flex-end"}.get(st.get("align"), "center")
    css["align-items"] = {"top": "flex-start", "bottom": "flex-end"}.get(st.get("verticalAlign"), "center")
    pad = float(st.get("spacing", "2"))
    css["padding"] = (f"{float(st.get('spacingTop', pad)) + 2}px {pad + 2}px {pad}px "
                      f"{float(st.get('spacingLeft', pad)) + 2}px")
    return css


def ortho_path(a, a_dir, pts, b, b_dir):
    """출구/입구 방향을 지키는 직교 경로 점 목록."""
    seq = [a] + pts + [b]
    out = [a]
    for k in range(1, len(seq)):
        p, q = out[-1], seq[k]
        if p[0] != q[0] and p[1] != q[1]:
            first, last = k == 1, k == len(seq) - 1
            if first and last and a_dir == b_dir:          # Z 자 경로
                if a_dir == "v":
                    my = (p[1] + q[1]) / 2
                    out += [(p[0], my), (q[0], my)]
                else:
                    mx = (p[0] + q[0]) / 2
                    out += [(mx, p[1]), (mx, q[1])]
            elif (first and a_dir == "v") or (last and b_dir == "h"):
                out.append((p[0], q[1]))
            else:
                out.append((q[0], p[1]))
        out.append(q)
    return out


def midpoint(path):
    segs = [(p, q, abs(q[0] - p[0]) + abs(q[1] - p[1])) for p, q in zip(path, path[1:])]
    half = sum(s[2] for s in segs) / 2
    for p, q, ln in segs:
        if half <= ln and ln:
            t = half / ln
            return p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
        half -= ln
    return path[-1]


def build():
    pages = [Page(i, s).build() for i, s in enumerate(STEPS)]
    base = pages[0]
    geo, vertices, edges = {}, [], []
    for c in base:
        if c.get("vertex") and not c.get("id").startswith("chip") and c.get("id") not in SKIP:
            g = c.find("mxGeometry")
            x, y, w, h = (float(g.get(k)) for k in ("x", "y", "width", "height"))
            geo[c.get("id")] = (x, y, w, h)
            vertices.append(dict(id=c.get("id"), x=x - VX, y=y - VY, w=w, h=h,
                                 cyl="cylinder" in c.get("style", "")))
    for c in base:
        if not c.get("edge"):
            continue
        st = style_dict(c.get("style"))

        def anchor(cid, kx, ky):
            x, y, w, h = geo[cid]
            fx, fy = float(st[kx]), float(st[ky])
            return (x + w * fx, y + h * fy), ("v" if fy in (0.0, 1.0) and fx not in (0.0, 1.0) else "h")

        a, ad = anchor(c.get("source"), "exitX", "exitY")
        b, bd = anchor(c.get("target"), "entryX", "entryY")
        pts = [(float(p.get("x")), float(p.get("y"))) for p in c.iter("mxPoint")]
        path = [(x - VX, y - VY) for x, y in ortho_path(a, ad, pts, b, bd)]
        lx, ly = midpoint(path)
        edges.append(dict(id=c.get("id"), d="M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in path),
                          both="startArrow=block" in c.get("style"), lx=lx, ly=ly))

    states = []
    for i, root in enumerate(pages):
        v, e = {}, {}
        for c in root:
            cid = c.get("id")
            if c.get("vertex") and cid in geo:
                v[cid] = dict(html=c.get("value", ""), css=vertex_css(c))
            elif c.get("edge"):
                st = style_dict(c.get("style"))
                e[cid] = dict(label=c.get("value", ""), color=st["strokeColor"], width=st["strokeWidth"],
                              dashed=st.get("dashed") == "1", anim=st.get("flowAnimation") == "1",
                              fc=st.get("fontColor"))
        states.append(dict(v=v, e=e, tab=STEPS[i]["tab"], title=STEPS[i]["title"], desc=STEPS[i]["desc"]))
    return vertices, edges, states


TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pod 생성 흐름</title>
<style>
  :root {
    --bg: #F6F7F9; --panel: #FFFFFF; --ink: #212529; --muted: #6C757D; --line: #DEE2E6;
    --accent: #E8590C; --accent-soft: #FFE8CC;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink);
         font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans KR", system-ui, sans-serif; }
  .wrap { max-width: 1600px; margin: 0 auto; padding: 20px 16px 40px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: var(--muted); font-size: 14px; margin: 0 0 16px; }
  .sub code { background: #EEF0F3; padding: 1px 6px; border-radius: 4px; }

  .chips { display: grid; grid-template-columns: repeat(10, 1fr); gap: 6px; margin-bottom: 12px; }
  .chip { border: 0; border-radius: 999px; padding: 8px 4px; font: inherit; font-size: 12.5px; cursor: pointer;
          background: #E9ECEF; color: #495057; transition: background .25s, color .25s; white-space: nowrap;
          overflow: hidden; text-overflow: ellipsis; }
  .chip.done { background: var(--accent-soft); }
  .chip.cur { background: var(--accent); color: #fff; font-weight: 700; }
  .chip:focus-visible, .ctl button:focus-visible { outline: 3px solid #4263EB; outline-offset: 2px; }

  .ctl { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .ctl button { border: 1px solid var(--line); background: var(--panel); border-radius: 8px; padding: 7px 14px;
                font: inherit; font-size: 14px; cursor: pointer; color: var(--ink); }
  .ctl button:hover { border-color: #ADB5BD; }
  .ctl button.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 700; }
  .ctl .title { font-size: 17px; font-weight: 700; color: var(--accent); margin-left: 8px; }
  .ctl .hint { margin-left: auto; color: var(--muted); font-size: 12px; }
  .bar { height: 4px; background: #E9ECEF; border-radius: 2px; overflow: hidden; margin-bottom: 12px; }
  .bar > i { display: block; height: 100%; width: 0; background: var(--accent); transition: width .4s; }

  .viewport { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; overflow: hidden;
              position: relative; }
  .stage { position: absolute; left: 0; top: 0; width: __VW__px; height: __VH__px; transform-origin: 0 0; }
  .v { position: absolute; display: flex; line-height: 1.35; overflow: visible;
       transition: border-color .35s, background-color .35s, box-shadow .35s, opacity .35s; }
  .v > div { width: 100%; }
  .v.cyl { border-radius: 50% / 14px !important; }
  .v.cyl::before { content: ""; position: absolute; left: -1px; right: -1px; top: -1px; height: 26px;
                   border: inherit; border-radius: 50%; }
  .v code { font-family: ui-monospace, Menlo, Consolas, monospace; }
  svg.edges { position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }
  svg.edges > path { fill: none; transition: stroke .35s, stroke-width .35s; }
  svg.edges path.anim { stroke-dasharray: 9 6; animation: flow .6s linear infinite; }
  @keyframes flow { to { stroke-dashoffset: -15; } }
  .lbl { position: absolute; transform: translate(-50%, -50%); background: #fff; font-size: 11px; font-weight: 700;
         text-align: center; padding: 1px 4px; border-radius: 4px; white-space: nowrap; line-height: 1.3;
         transition: opacity .3s; }
  .lbl:empty { display: none; }
  .pop { animation: pop .45s ease-out; }
  @keyframes pop { from { transform: scale(.92); opacity: .3; } to { transform: none; opacity: 1; } }

  .desc { margin-top: 14px; background: var(--panel); border: 1px solid var(--line); border-left: 5px solid var(--accent);
          border-radius: 12px; padding: 16px 20px; font-size: 15px; line-height: 1.75; }
  .desc h2 { margin: 0 0 8px; font-size: 18px; color: var(--accent); }
  .desc code { background: #F1F3F5; padding: 1px 6px; border-radius: 4px; font-size: 13.5px;
               font-family: ui-monospace, Menlo, Consolas, monospace; }
  .legend { display: flex; gap: 18px; flex-wrap: wrap; color: var(--muted); font-size: 12.5px; margin-top: 10px; }
  .legend span::before { content: ""; display: inline-block; width: 22px; height: 0; vertical-align: middle;
                         margin-right: 6px; border-top: 3px solid; }
  .legend .l1::before { border-color: #E03131; border-top-style: dashed; }
  .legend .l2::before { border-color: #C4C4C4; border-top-style: dashed; border-top-width: 2px; }
  .legend .l3::before { width: 14px; height: 10px; border: 3px solid var(--accent); border-radius: 3px; }

  @media (max-width: 900px) {
    .chips { grid-template-columns: repeat(5, 1fr); }
    .ctl .hint { display: none; }
    .ctl .title { width: 100%; margin: 4px 0 0; font-size: 15px; }
    .desc { font-size: 14px; padding: 14px; }
  }
  @media (prefers-reduced-motion: reduce) {
    svg.edges path.anim { animation: none; }
    .pop { animation: none; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>kubectl 로 Pod 6개를 만들 때 쿠버네티스 클러스터 안에서 일어나는 일</h1>
  <p class="sub"><code>kubectl apply -f nginx-deploy.yaml</code> (Deployment, replicas: 6) — 단계를 눌러 보거나 ▶ 자동 재생을 켜 보세요.</p>

  <nav class="chips" id="chips" aria-label="단계"></nav>
  <div class="ctl">
    <button id="prev" aria-label="이전 단계">◀ 이전</button>
    <button id="play" class="primary">▶ 자동 재생</button>
    <button id="next" aria-label="다음 단계">다음 ▶</button>
    <span class="title" id="stitle"></span>
    <span class="hint">키보드 ← → 로 이동, Space 로 재생/정지</span>
  </div>
  <div class="bar"><i id="bar"></i></div>

  <div class="viewport" id="viewport">
    <div class="stage" id="stage">
      <svg class="edges" id="svg" width="__VW__" height="__VH__" viewBox="0 0 __VW__ __VH__">
        <defs id="defs"></defs>
      </svg>
    </div>
  </div>

  <section class="desc" aria-live="polite">
    <h2 id="dtitle"></h2>
    <div id="dbody"></div>
    <div class="legend">
      <span class="l1">이번 단계에서 오가는 요청 (움직이는 화살표)</span>
      <span class="l2">대기 중인 통신 경로</span>
      <span class="l3">이번 단계에서 일하는 컴포넌트</span>
    </div>
  </section>
</div>

<script>
const VERTICES = __VERTICES__;
const EDGES = __EDGES__;
const STATES = __STATES__;
const AUTOPLAY_MS = 4500;

const stage = document.getElementById("stage");
const svg = document.getElementById("svg");
const defs = document.getElementById("defs");
const NS = "http://www.w3.org/2000/svg";
const vEl = {}, eEl = {}, lEl = {}, markers = {};

function marker(color) {
  if (markers[color]) return markers[color];
  const id = "m" + Object.keys(markers).length;
  const m = document.createElementNS(NS, "marker");
  m.setAttribute("id", id); m.setAttribute("viewBox", "0 0 10 10"); m.setAttribute("refX", "9");
  m.setAttribute("refY", "5"); m.setAttribute("markerWidth", "5"); m.setAttribute("markerHeight", "5");
  m.setAttribute("orient", "auto-start-reverse"); m.setAttribute("markerUnits", "strokeWidth");
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", "M0,0 L10,5 L0,10 z"); p.setAttribute("fill", color);
  m.appendChild(p); defs.appendChild(m);
  return (markers[color] = `url(#${id})`);
}

// 정적 배치: 사각형 → 화살표 → 라벨 순서 (라벨이 항상 위)
for (const v of VERTICES) {
  const d = document.createElement("div");
  d.className = "v" + (v.cyl ? " cyl" : "");
  Object.assign(d.style, { left: v.x + "px", top: v.y + "px", width: v.w + "px", height: v.h + "px" });
  d.appendChild(document.createElement("div"));
  stage.insertBefore(d, svg);
  vEl[v.id] = d;
}
for (const e of EDGES) {
  const p = document.createElementNS(NS, "path");
  p.setAttribute("d", e.d);
  svg.appendChild(p);
  eEl[e.id] = p;
  const l = document.createElement("div");
  l.className = "lbl";
  Object.assign(l.style, { left: e.lx + "px", top: e.ly + "px" });
  stage.appendChild(l);
  lEl[e.id] = l;
}
const edgeMeta = Object.fromEntries(EDGES.map(e => [e.id, e]));

const chips = document.getElementById("chips");
STATES.forEach((s, i) => {
  const b = document.createElement("button");
  b.className = "chip"; b.textContent = s.tab; b.title = s.title;
  b.onclick = () => { stop(); go(i); };
  chips.appendChild(b);
});

let cur = -1;
function go(i) {
  i = (i + STATES.length) % STATES.length;
  const s = STATES[i];
  for (const [id, st] of Object.entries(s.v)) {
    const el = vEl[id];
    if (el.firstChild.innerHTML !== st.html) {
      el.firstChild.innerHTML = st.html;
      if (cur >= 0 && id.startsWith("pod")) { el.classList.remove("pop"); void el.offsetWidth; el.classList.add("pop"); }
    }
    for (const [k, val] of Object.entries(st.css)) el.style.setProperty(k, val);
  }
  for (const [id, st] of Object.entries(s.e)) {
    const p = eEl[id];
    p.setAttribute("stroke", st.color);
    p.setAttribute("stroke-width", st.width);
    p.setAttribute("stroke-dasharray", st.dashed ? "5 4" : (st.anim ? "9 6" : "none"));
    p.classList.toggle("anim", st.anim);
    p.setAttribute("marker-end", marker(st.color));
    if (edgeMeta[id].both) p.setAttribute("marker-start", marker(st.color)); else p.removeAttribute("marker-start");
    lEl[id].innerHTML = st.label;
    lEl[id].style.color = st.fc;
  }
  // 강조된 화살표는 맨 위로
  for (const [id, st] of Object.entries(s.e)) if (st.anim || i === 0) svg.appendChild(eEl[id]);

  [...chips.children].forEach((c, k) => {
    c.classList.toggle("cur", k === i);
    c.classList.toggle("done", i !== 0 && k < i);
    c.setAttribute("aria-current", k === i ? "step" : "false");
  });
  document.getElementById("stitle").innerHTML = s.title;
  document.getElementById("dtitle").innerHTML = s.title;
  document.getElementById("dbody").innerHTML = s.desc;
  document.getElementById("bar").style.width = (i / (STATES.length - 1) * 100) + "%";
  cur = i;
}

let timer = null;
const playBtn = document.getElementById("play");
function stop() { clearInterval(timer); timer = null; playBtn.textContent = "▶ 자동 재생"; }
function play() {
  if (cur === STATES.length - 1) go(1); else if (cur === 0) go(1);
  timer = setInterval(() => { if (cur >= STATES.length - 1) stop(); else go(cur + 1); }, AUTOPLAY_MS);
  playBtn.textContent = "❚❚ 정지";
}
playBtn.onclick = () => (timer ? stop() : play());
document.getElementById("prev").onclick = () => { stop(); go(cur - 1); };
document.getElementById("next").onclick = () => { stop(); go(cur + 1); };
document.addEventListener("keydown", e => {
  if (e.key === "ArrowRight") { stop(); go(cur + 1); }
  else if (e.key === "ArrowLeft") { stop(); go(cur - 1); }
  else if (e.key === " " && e.target === document.body) { e.preventDefault(); timer ? stop() : play(); }
});

// 화면 폭에 맞춰 다이어그램 축소
const viewport = document.getElementById("viewport");
function fit() {
  const k = Math.min(1, viewport.clientWidth / __VW__);
  stage.style.transform = `scale(${k})`;
  viewport.style.height = (__VH__ * k) + "px";
}
new ResizeObserver(fit).observe(viewport);
fit();
go(0);
</script>
</body>
</html>
"""


def main():
    vertices, edges, states = build()
    html = (TEMPLATE
            .replace("__VERTICES__", json.dumps(vertices, ensure_ascii=False))
            .replace("__EDGES__", json.dumps(edges, ensure_ascii=False))
            .replace("__STATES__", json.dumps(states, ensure_ascii=False))
            .replace("__VW__", str(VW)).replace("__VH__", str(VH)))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
