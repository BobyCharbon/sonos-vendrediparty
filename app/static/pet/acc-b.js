// 🪩 Compagnon — accessoires de la collection (lot A), 2/2 : dos, pieds, facettes, effets, décor, petit compagnon.
// Même gabarit que acc-a.js : un dessin par objet, posé sur son point d'ancrage (skin.js), mis à l'échelle du stade.
(function () {
  "use strict";
  const S = window.PetSkin;
  if (!S) return;
  const INK = "#1b1030";
  const r1 = (v) => Math.round(v * 10) / 10;
  const k = (a) => r1(a.body.r / 57 * 100) / 100;
  const at = (x, y, kk, inner, rot) => `<g transform="translate(${r1(x)} ${r1(y)})${rot ? ` rotate(${rot})` : ""} scale(${kk})">${inner}</g>`;
  const line = (d, c, w, extra) => `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"${extra ? " " + extra : ""}/>`;
  const shape = (d, fill, sw, extra) => `<path d="${d}" fill="${fill}" stroke="${INK}" stroke-width="${sw ?? 1.6}" stroke-linejoin="round"${extra ? " " + extra : ""}/>`;
  const dot = (x, y, r, fill, extra) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"${extra ? " " + extra : ""}/>`;
  const fx = (i) => `class="pt-fx" style="animation-delay:${(i % 8) * 0.3}s"`;
  const star = (x, y, s, c, i) => `<path ${fx(i || 0)} d="M${x} ${y - s} L${r1(x + s * 0.28)} ${r1(y - s * 0.28)} L${x + s} ${y} L${r1(x + s * 0.28)} ${r1(y + s * 0.28)} L${x} ${y + s} L${r1(x - s * 0.28)} ${r1(y + s * 0.28)} L${x - s} ${y} L${r1(x - s * 0.28)} ${r1(y - s * 0.28)} Z" fill="${c}"/>`;
  const def = (id, slot, draw, more) => S.defineAccessory({ id, slot, label: id, draw, ...(more || {}) });

  // ── Gabarits ──
  const onBack = (inner) => ({ a }) => at(a.back.x, a.back.y, k(a), inner);
  // Pieds : une chaussure par pied (dessin centré sur le pied, largeur adulte 26), posée sur les pieds caoutchouc.
  const shoes = (one) => ({ a }) => {
    const kk = r1(a.feet.w / 26 * 1.15 * 100) / 100;
    return at(a.feet.l.x, a.feet.l.y, kk, one(-1)) + at(a.feet.r.x, a.feet.r.y, kk, one(1));
  };
  const PET = 1.8;   // assez grand pour se voir à côté de Zicou (widget compris)
  const pet = (inner, fly) => ({ a }) => at(Math.min(a.pet.x, 176), a.pet.y - (fly || 0) * PET, PET, inner);

  // ════ DOS ════
  def("sac-rando", "back", onBack(
    shape("M30 -58 Q62 -64 72 -34 L76 22 Q72 38 52 36 L34 34 Z", "#d1452b", 1.8) + shape("M58 -4 Q84 -4 84 16 L82 32 Q68 36 58 32 Z", "#a93421", 1.6)
    + line("M62 -46 L70 -6", "#ffd24d", 2.4) + shape("M14 -70 Q40 -80 62 -66 L64 -54 L16 -58 Z", "#4e6b8a", 1.6)
    + `<rect x="10" y="-80" width="58" height="9" rx="4.5" fill="#7a96b4" stroke="${INK}" stroke-width="1.4" transform="rotate(10)"/>`
  ));
  def("sac-magnesie", "back", onBack(
    line("M30 30 Q46 30 56 22", INK, 3) + shape("M54 16 Q54 0 70 0 Q86 0 86 16 L84 42 Q70 50 56 42 Z", "#f2f2f2", 1.8)
    + `<ellipse cx="70" cy="0" rx="16" ry="5" fill="#3ddc97" stroke="${INK}" stroke-width="1.6"/>`
    + line("M58 20 Q70 27 82 20", "#3ddc97", 2.6) + dot(63, -5, 2.4, "#fff") + dot(75, -7, 2, "#fff") + dot(70, -10, 1.6, "#fff")
  ));
  def("corde", "back", onBack(
    [0, 1, 2, 3].map((i) => `<ellipse cx="${-62 + i * 3}" cy="${-4 + i * 3}" rx="${24 - i * 3}" ry="${36 - i * 4}" fill="none" stroke="${INK}" stroke-width="6.5"/>`
      + `<ellipse cx="${-62 + i * 3}" cy="${-4 + i * 3}" rx="${24 - i * 3}" ry="${36 - i * 4}" fill="none" stroke="${["#ff4f9a", "#5ee7ff", "#ff4f9a", "#5ee7ff"][i]}" stroke-width="4" stroke-dasharray="5 3"/>`).join("")
  ));

  // ════ PIEDS ════
  def("baskets-compensees", "feet", shoes(() =>
    `<rect x="-15" y="2" width="30" height="8" rx="3" fill="#ffd24d" stroke="${INK}" stroke-width="1.6"/>`
    + shape("M-14 3 Q-14 -10 0 -10 Q12 -10 15 0 L15 3 Z", "#ff4f9a", 1.6) + line("M-6 -6 L4 -6 M-7 -2 L5 -2", "#fff", 1.4)
    + line("M-14 6 H15", "#fff6c4", 1.4)));
  def("chaussettes-laine", "feet", shoes(() =>
    shape("M-8 -26 L8 -26 L8 -4 Q16 -2 16 6 Q16 11 8 11 L-12 11 Q-15 11 -14 5 L-8 -4 Z", "#f4f0ff", 1.6)
    + [-20, -14].map((y) => line(`M-8 ${y} H8`, "#d1452b", 2.4)).join("") + line("M-6 2 L-2 6 L2 2 L6 6", "#d1452b", 1.6)));
  def("chaussons-escalade", "feet", shoes((d) =>
    shape(`M${-14 * d} 10 L${-14 * d} 0 Q${-12 * d} -9 ${2 * d} -8 Q${13 * d} -6 ${16 * d} 4 L${16 * d} 10 Z`, "#8f6bff", 1.6)
    + `<rect x="-15" y="7" width="31" height="4" rx="2" fill="${INK}"/>` + line(`M${-6 * d} -6 L${6 * d} 0`, "#ffd24d", 2)));
  def("bottes-citrouille", "feet", shoes(() =>
    shape("M-12 -14 L10 -14 L12 2 Q18 4 16 10 L-14 10 Z", "#ff8a2a", 1.6) + line("M-4 -14 Q-6 -2 -4 10 M4 -14 Q6 -2 4 10", "#e06a10", 1.2)
    + `<rect x="-14" y="-18" width="26" height="5" rx="2" fill="#5c9b4b" stroke="${INK}" stroke-width="1.2"/>`));
  def("escarpins-paillettes", "feet", shoes((d) =>
    shape(`M${-14 * d} 8 Q${-12 * d} -6 ${2 * d} -4 Q${14 * d} -2 ${16 * d} 8 Z`, "#ffd24d", 1.6)
    + line(`M${-11 * d} 8 L${-12 * d} 12`, INK, 2.4)
    + [-8, -2, 4, 10].map((x, i) => dot(x * d, 2 + (i % 2) * 2, 1.3, "#fff", fx(i))).join("")));
  def("baskets-led", "feet", shoes(() =>
    `<rect x="-15" y="5" width="30" height="5" rx="2.5" fill="#5ee7ff" ${fx(1)}/>`
    + shape("M-14 6 Q-14 -8 0 -8 Q12 -8 15 2 L15 6 Z", "#2d1d86", 1.6) + line("M-14 8 H15", INK, 1.2)
    + line("M-6 -4 L4 -4", "#ff4f9a", 1.6)));

  // ════ FACETTES (palette de la boule : base [clair, moyen, sombre], tuiles, accents [couleur, seuil cumulé]) ════
  S.defineAccessory({ id: "facettes-miroir", slot: "facets", label: "facettes-miroir", palette: {
    base: ["#f2f4ff", "#a6abc8", "#4b4f6b"], tiles: ["#ffffff", "#e3e6f5", "#c3c8de", "#9aa0bd"], accents: [["#ff9be0", 0.08], ["#9be8ff", 0.16]] } });
  S.defineAccessory({ id: "facettes-or", slot: "facets", label: "facettes-or", palette: {
    base: ["#fff2b8", "#e2a93a", "#7a4e10"], tiles: ["#ffe27a", "#ffd24d", "#f2b632", "#fff6c4"], accents: [["#ffffff", 0.14], ["#ff9b3d", 0.22]] } });
  S.defineAccessory({ id: "facettes-squelette", slot: "facets", label: "facettes-squelette", palette: {
    base: ["#3a3550", "#1a1626", "#07060c"], tiles: ["#211d30", "#2d283f", "#15121f", "#3a3550"], accents: [["#8be36b", 0.16], ["#d6ffb8", 0.24]] } });
  S.defineAccessory({ id: "m-montagne", slot: "facets", label: "m-montagne", palette: {
    base: ["#f2fbff", "#7fc8e8", "#1f4f7a"], tiles: ["#d7f3ff", "#a8e1f7", "#ffffff", "#7fc8e8"], accents: [["#ffc4f0", 0.08], ["#c4b5ff", 0.16], ["#fff", 0.3]] } });

  // ════ EFFETS ({ back, front }) ════
  def("nuage-magnesie", "effect", ({ a }) => {
    const { x, y, r } = a.body, g = a.ground.y;
    const puff = (px, py, s, i) => `<g ${fx(i)}>${[[-1, 0], [0, -0.6], [1, 0], [0.4, 0.4], [-0.5, 0.4]].map(([dx, dy]) => dot(r1(px + dx * s), r1(py + dy * s), r1(s * 0.75), "#ffffff", 'opacity=".8"')).join("")}</g>`;
    return { back: puff(x - r * 1.05, g - 14, 9, 0) + puff(x + r * 1.1, g - 20, 7, 3),
      front: puff(x - r * 0.4, g - 3, 6, 1) + puff(x + r * 0.55, g - 2, 7, 2) + dot(r1(x + r * 0.9), r1(y - r * 0.2), 2, "#fff", fx(4)) };
  });
  def("m-escalade", "effect", ({ a, uid }) => {
    const { x, y, r } = a.body;
    return {
      back: `<radialGradient id="${uid}summit"><stop offset=".55" stop-color="#ffe66b" stop-opacity="0"/><stop offset=".75" stop-color="#ffb547" stop-opacity=".55"/><stop offset=".88" stop-color="#ff4f9a" stop-opacity=".45"/><stop offset="1" stop-color="#8f6bff" stop-opacity="0"/></radialGradient>`
        + `<circle cx="${x}" cy="${r1(y - r * 0.1)}" r="${r1(r * 1.65)}" fill="url(#${uid}summit)" class="pt-fx"/>`
        + `<path d="M${r1(x - r * 1.9)} ${a.ground.y} L${r1(x - r * 0.9)} ${r1(y - r * 0.9)} L${r1(x - r * 0.5)} ${r1(y - r * 0.5)} L${r1(x + r * 0.2)} ${r1(y - r * 1.4)} L${r1(x + r * 1.9)} ${a.ground.y} Z" fill="#2a3f6b" opacity=".55"/>`
        + `<path d="M${r1(x + r * 0.2)} ${r1(y - r * 1.4)} L${r1(x - r * 0.05)} ${r1(y - r * 1.05)} L${r1(x + r * 0.45)} ${r1(y - r * 1.05)} Z" fill="#fff" opacity=".8"/>`,
      front: star(r1(x - r * 1.15), r1(y - r * 0.7), 4, "#ffe66b", 1) + star(r1(x + r * 1.2), r1(y - r * 0.4), 3, "#fff", 4)
        + star(r1(x + r * 0.3), r1(y - r * 1.55), 3.5, "#ffb547", 6),
    };
  });
  def("brume", "effect", ({ a }) => {
    const { x, r } = a.body, g = a.ground.y;
    const band = (yy, w, op, i) => `<ellipse ${fx(i)} cx="${r1(x + (i % 2 ? 10 : -10))}" cy="${r1(yy)}" rx="${r1(w)}" ry="6" fill="#b9a6ff" opacity="${op}"/>`;
    return { back: band(g - 26, r * 1.9, 0.35, 0) + band(g - 40, r * 1.6, 0.25, 3), front: band(g - 6, r * 1.7, 0.5, 1) + band(g + 2, r * 2, 0.35, 2) };
  });
  def("m-halloween", "effect", ({ a, uid }) => {
    const { x, y, r } = a.body, mx = x - r * 0.95, my = y - r * 1.15;
    const bat = (bx, by, s, i) => `<path ${fx(i)} transform="translate(${r1(bx)} ${r1(by)}) scale(${s})" d="M0 0 Q-4 -5 -10 -3 Q-7 0 -8 3 Q-4 1 0 3 Q4 1 8 3 Q7 0 10 -3 Q4 -5 0 0 Z" fill="${INK}"/>`;
    return {
      back: `<radialGradient id="${uid}moon"><stop offset=".6" stop-color="#ffe9a8"/><stop offset="1" stop-color="#ffb547" stop-opacity="0"/></radialGradient>`
        + `<circle cx="${r1(mx)}" cy="${r1(my)}" r="${r1(r * 0.75)}" fill="url(#${uid}moon)" class="pt-fx"/>`
        + `<circle cx="${r1(mx)}" cy="${r1(my)}" r="${r1(r * 0.5)}" fill="#fff4cf"/><circle cx="${r1(mx + r * 0.12)}" cy="${r1(my - r * 0.1)}" r="${r1(r * 0.08)}" fill="#f0dc9e"/>`
        + `<circle cx="${r1(mx - r * 0.18)}" cy="${r1(my + r * 0.15)}" r="${r1(r * 0.06)}" fill="#f0dc9e"/>`,
      front: bat(x + r * 1.1, y - r * 1.2, 1.2, 0) + bat(x + r * 1.45, y - r * 0.8, 0.9, 3) + bat(mx + r * 0.2, my + r * 0.6, 0.8, 5),
    };
  });
  def("confettis", "effect", ({ a }) => {
    const { x, y, r } = a.body, cols = ["#ff4f9a", "#ffd24d", "#5ee7ff", "#8be36b", "#8f6bff"];
    let out = "";
    for (let i = 0; i < 18; i += 1) {
      const px = x - r * 1.6 + (i * 37 % 100) / 100 * r * 3.2, py = y - r * 1.5 + (i * 53 % 100) / 100 * r * 1.6;
      if (Math.abs(px - x) < r * 0.9 && py > y - r * 1.05) continue;
      out += `<rect ${fx(i)} x="${r1(px - 2.5)}" y="${r1(py - 1.2)}" width="5" height="2.4" rx=".8" fill="${cols[i % 5]}" transform="rotate(${(i * 47) % 180} ${r1(px)} ${r1(py)})"/>`;
    }
    return { back: "", front: out };
  });
  def("feu-artifice", "effect", ({ a }) => {
    const { x, y, r } = a.body;
    const burst = (bx, by, s, c, i) => `<g ${fx(i)}>${Array.from({ length: 12 }, (_, j) => {
      const t = j * Math.PI / 6;
      return line(`M${r1(bx + Math.cos(t) * s * 0.35)} ${r1(by + Math.sin(t) * s * 0.35)} L${r1(bx + Math.cos(t) * s)} ${r1(by + Math.sin(t) * s)}`, c, 1.8);
    }).join("")}${dot(r1(bx), r1(by), 1.8, "#fff")}</g>`;
    return { back: burst(x - r * 1.15, y - r * 1.05, r * 0.42, "#ff4f9a", 0) + burst(x + r * 1.2, y - r * 1.25, r * 0.36, "#ffd24d", 3)
      + burst(x + r * 0.15, y - r * 1.7, r * 0.3, "#5ee7ff", 5), front: "" };
  });
  def("projecteurs", "effect", ({ a, uid }) => {
    const { x, y, r } = a.body, g = a.ground.y;
    const beam = (sx, c, i) => `<path ${fx(i)} d="M${sx} 4 L${r1(x - r * 0.7)} ${g} L${r1(x + r * 0.7)} ${g} Z" fill="url(#${uid}beam${i})" opacity=".55"/>`
      + `<linearGradient id="${uid}beam${i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c}"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></linearGradient>`
      + `<rect x="${sx - 6}" y="0" width="12" height="8" rx="2" fill="${INK}"/>`;
    return { back: beam(14, "#ffe66b", 0) + beam(186, "#5ee7ff", 2) + `<ellipse cx="${x}" cy="${g - 1}" rx="${r1(r * 1.1)}" ry="5" fill="#ffe66b" opacity=".35"/>`,
      front: star(r1(x - r * 0.9), r1(y - r * 1.15), 4, "#fff", 1) + star(r1(x + r), r1(y - r * 0.95), 3, "#ffe66b", 3) };
  });

  // ════ DÉCOR (fond 200 × 200, sous tout le reste) ════
  def("decor-piste", "decor", () => {
    let tiles = "";
    for (let i = 0; i < 6; i += 1) for (let j = 0; j < 3; j += 1) {
      tiles += `<rect ${fx(i + j)} x="${i * 34 - 4}" y="${150 + j * 17}" width="32" height="15" rx="2" fill="${["#ff4f9a", "#5ee7ff", "#ffd24d", "#8f6bff"][(i + j) % 4]}" opacity=".55"/>`;
    }
    return `<rect width="200" height="200" fill="#1a0f3d"/>${tiles}`
      + line("M100 0 V18", "#c9c2ea", 1.4) + dot(100, 28, 10, "#c9c2ea", `stroke="${INK}" stroke-width="1.4"`)
      + [-1, 1].map((d, i) => `<path ${fx(i)} d="M100 30 L${100 + d * 90} 150 L${100 + d * 60} 150 Z" fill="#fff" opacity=".07"/>`).join("")
      + star(30, 30, 3, "#fff", 2) + star(170, 44, 2.5, "#5ee7ff", 4);
  });
  def("decor-chalet", "decor", () =>
    `<rect width="200" height="200" fill="#bfe3ff"/><path d="M0 120 L50 50 L80 90 L120 30 L200 120 Z" fill="#e9f4ff"/><path d="M50 50 L40 64 L62 66 Z M120 30 L106 50 L134 50 Z" fill="#fff"/>`
    + `<rect y="140" width="200" height="60" fill="#f7fbff"/>`
    + shape("M142 110 L170 86 L198 110 Z", "#8a4a22", 1.6) + `<rect x="148" y="110" width="44" height="32" fill="#b06a35" stroke="${INK}" stroke-width="1.6"/>`
    + `<rect x="156" y="118" width="10" height="10" fill="#ffe27a" stroke="${INK}" stroke-width="1"/><rect x="174" y="118" width="10" height="10" fill="#ffe27a" stroke="${INK}" stroke-width="1"/>`
    + shape("M138 112 L170 84 L202 112 L196 114 L170 92 L144 114 Z", "#fff", 1.2)
    + [[20, 30], [60, 20], [95, 60], [30, 90], [185, 40], [12, 150]].map(([sx, sy], i) => dot(sx, sy, 2, "#fff", fx(i))).join(""));
  def("decor-mur", "decor", () => {
    const holds = [[20, 30, "#ff4f9a"], [56, 60, "#ffd24d"], [32, 96, "#3ddc97"], [150, 24, "#5ee7ff"], [178, 70, "#ff8a2a"], [160, 120, "#8f6bff"], [16, 150, "#ffd24d"], [186, 160, "#ff4f9a"]];
    return `<rect width="200" height="200" fill="#d9c7a8"/>` + [0, 1, 2, 3].map((i) => line(`M0 ${i * 50 + 25} H200`, "#c4ae8a", 1.2)).join("")
      + [0, 1, 2, 3].map((i) => line(`M${i * 50 + 25} 0 V200`, "#c4ae8a", 1.2)).join("")
      + holds.map(([hx, hy, c]) => shape(`M${hx - 7} ${hy} Q${hx - 6} ${hy - 7} ${hx} ${hy - 6} Q${hx + 8} ${hy - 5} ${hx + 6} ${hy + 3} Q${hx} ${hy + 7} ${hx - 7} ${hy} Z`, c, 1.4)).join("")
      + `<rect y="176" width="200" height="24" fill="#5c4a8a" opacity=".6"/>`;
  });
  def("decor-manoir", "decor", () =>
    `<rect width="200" height="200" fill="#1c1338"/>` + dot(160, 36, 16, "#fff4cf") + dot(166, 32, 14, "#1c1338")
    + `<path d="M20 160 L20 90 L40 70 L60 90 L60 120 L90 120 L90 70 L105 50 L120 70 L120 160 Z" fill="#0d0820"/>`
    + `<rect x="28" y="98" width="8" height="10" fill="#ffe27a" ${fx(1)}/><rect x="98" y="80" width="8" height="10" fill="#ffe27a" ${fx(3)}/><rect x="70" y="128" width="8" height="10" fill="#ffe27a"/>`
    + `<rect y="160" width="200" height="40" fill="#120b28"/>` + [[70, 30], [30, 20], [190, 90], [140, 100]].map(([sx, sy], i) => dot(sx, sy, 1.2, "#fff", fx(i))).join(""));
  def("decor-minuit", "decor", () =>
    `<rect width="200" height="200" fill="#0f1440"/>` + `<path d="M0 170 V130 H18 V110 H34 V140 H48 V96 H70 V150 H86 V120 H104 V140 H124 V100 H140 V130 H160 V116 H180 V140 H200 V170 Z" fill="#070a24"/>`
    + [[24, 120], [52, 108], [60, 126], [128, 112], [146, 136], [170, 124]].map(([wx, wy]) => `<rect x="${wx}" y="${wy}" width="4" height="5" fill="#ffe27a"/>`).join("")
    + `<rect y="170" width="200" height="30" fill="#151b52"/>`
    + [[40, 40, "#ff4f9a"], [150, 30, "#ffd24d"], [100, 56, "#5ee7ff"]].map(([bx, by, c], i) => `<g ${fx(i)}>${Array.from({ length: 10 }, (_, j) => {
      const t = j * Math.PI / 5;
      return line(`M${r1(bx + Math.cos(t) * 4)} ${r1(by + Math.sin(t) * 4)} L${r1(bx + Math.cos(t) * 13)} ${r1(by + Math.sin(t) * 13)}`, c, 1.4);
    }).join("")}</g>`).join(""));
  def("decor-salon", "decor", () =>
    `<rect width="200" height="200" fill="#3a2366"/><rect y="150" width="200" height="50" fill="#5a3a2a"/>`
    + line("M0 22 Q50 40 100 22 Q150 40 200 22", "#1b1030", 1.2)
    + [12, 30, 48, 66, 84, 116, 134, 152, 170, 188].map((lx, i) => dot(lx, 22 + Math.sin(lx / 32) * 9 + 5, 3, ["#ffd24d", "#ff4f9a", "#5ee7ff", "#8be36b"][i % 4], fx(i))).join("")
    + shape("M6 150 L6 122 Q6 112 18 112 L52 112 Q64 112 64 122 L64 150 Z", "#ff4f9a", 1.6) + shape("M2 130 H10 V152 H2 Z M60 130 H68 V152 H60 Z", "#d63c80", 1.4)
    + line("M176 150 V90", INK, 2) + shape("M164 90 L188 90 L182 72 L170 72 Z", "#ffd24d", 1.4) + dot(176, 96, 14, "#ffe66b", 'opacity=".18"'));

  // ════ PETIT COMPAGNON (au sol, à droite de Zicou ; certains volent) ════
  def("marmotte", "pet", pet(
    `<ellipse cx="0" cy="-1" rx="11" ry="3" fill="#000" opacity=".25"/>`
    + shape("M-9 -2 Q-12 -20 -4 -26 Q0 -30 4 -26 Q12 -20 9 -2 Z", "#a8743f", 1.6) + shape("M-5 -6 Q0 -18 5 -6 Z", "#e8c79a", 0)
    + dot(-3.2, -21, 1.6, INK) + dot(3.2, -21, 1.6, INK) + `<ellipse cx="0" cy="-17.5" rx="2" ry="1.4" fill="${INK}"/>`
    + `<rect x="-1.6" y="-16.2" width="3.2" height="2.6" rx=".6" fill="#fff" stroke="${INK}" stroke-width=".6"/>`
    + dot(-6, -26, 2.4, "#a8743f", `stroke="${INK}" stroke-width="1.2"`) + dot(6, -26, 2.4, "#a8743f", `stroke="${INK}" stroke-width="1.2"`)
    + line("M-4 -10 L-7 -12 M4 -10 L7 -12", INK, 1.6)));
  def("chauve-souris", "pet", pet(
    `<g class="pt-fx">` + shape("M0 0 Q-6 -8 -18 -6 Q-14 -2 -15 3 Q-9 0 -6 4 Q-3 1 0 3 Q3 1 6 4 Q9 0 15 3 Q14 -2 18 -6 Q6 -8 0 0 Z", "#2a1b52", 1.4)
    + dot(0, -2, 5, "#2a1b52", `stroke="${INK}" stroke-width="1.2"`) + dot(-2, -3, 1.1, "#ffe27a") + dot(2, -3, 1.1, "#ffe27a")
    + shape("M-3 -6 L-4 -10 L-1 -7 Z M3 -6 L4 -10 L1 -7 Z", "#2a1b52", 1) + "</g>", 42));
  def("lumi", "pet", pet(
    `<circle r="14" fill="#ffe66b" opacity=".25" class="pt-fx"/>` + `<ellipse cx="0" cy="4" rx="5" ry="6" fill="#fff38a" stroke="${INK}" stroke-width="1.2" class="pt-fx"/>`
    + dot(0, -4, 5, "#8f6bff", `stroke="${INK}" stroke-width="1.2"`) + dot(-1.8, -4.5, 1.1, "#fff") + dot(1.8, -4.5, 1.1, "#fff")
    + `<ellipse cx="-7" cy="-2" rx="5" ry="3" fill="#bff0ff" fill-opacity=".7" stroke="${INK}" stroke-width=".8" transform="rotate(-25 -7 -2)"/>`
    + `<ellipse cx="7" cy="-2" rx="5" ry="3" fill="#bff0ff" fill-opacity=".7" stroke="${INK}" stroke-width=".8" transform="rotate(25 7 -2)"/>`
    + line("M-2 -9 L-4 -13 M2 -9 L4 -13", INK, 1), 48));
  // Mythique Nouvel An : le Phénix de minuit, oiseau de flammes dorées.
  def("m-nouvelan", "pet", pet(
    `<g class="pt-fx">` + shape("M0 -6 Q-22 -26 -26 -6 Q-16 -10 -10 -2 Q-18 2 -14 10 Q-6 2 0 4 Z", "#ff8a2a", 1.4)
    + shape("M0 -6 Q22 -26 26 -6 Q16 -10 10 -2 Q18 2 14 10 Q6 2 0 4 Z", "#ffb547", 1.4) + "</g>"
    + shape("M-4 0 Q0 -14 4 0 Q6 10 0 18 Q-6 10 -4 0 Z", "#ffd24d", 1.4)
    + shape("M-3 16 Q0 26 -6 30 M3 16 Q2 24 6 30", "none", 1.6) + line("M0 18 Q-2 26 -6 30 M0 18 Q2 26 6 30", "#ff4f9a", 2)
    + dot(0, -9, 5, "#ffd24d", `stroke="${INK}" stroke-width="1.2"`) + dot(-1.6, -10, 1, INK) + dot(1.6, -10, 1, INK)
    + shape("M-1.5 -7.5 L0 -5 L1.5 -7.5 Z", "#ff8a2a", .8) + shape("M0 -14 Q-3 -20 -1 -22 Q1 -18 2 -21 Q4 -18 0 -14 Z", "#ff4f9a", 1)
    + star(-14, -18, 2.5, "#fff", 2) + star(16, 4, 2, "#ffe66b", 5), 46));
})();
