// 🪩 Compagnon — COUCHE GRAPHIQUE (skin) : « Zicou Nuit », la mascotte choisie par l'admin (4.11.2026).
// Boule à facettes violet nuit, grosse tête ronde de bébé, toutes petites jambes, casque fin à oreillettes et deux
// antennes à LED d'humeur, gros pieds caoutchouc. Dessin 100 % code (SVG), sans fichier externe.
//
// ── CONTRAT (inchangé, lu par pet.js et games.js) ──────────────────────────────────────────────────────────────────
// window.PetSkin = { id, creatureName, render(opts) → chaîne SVG, moodColor(emotion) → couleur CSS, …accessoires }.
//   opts = { stage: "egg"|"baby"|"teen"|"adult"|"dead", variant: "star"|"classic"|"wild",
//            emotion: "egg"|"happy"|"party"|"hungry"|"tired"|"sad"|"sick"|"sleep"|"ghost",
//            outfit: null|id d'une tenue (app/pet.py OUTFITS), label: texte VoiceOver,
//            accessories?: { [emplacement]: id }  (facultatif, voir plus bas), shiny?: true (Zicou chrome),
//            dyes?: { [id d'accessoire]: "rose" | "or" | "menthe" | "nuit" | "corail" } (teintures) }
// Le SVG fait 200 × 200 (viewBox "0 0 200 200"). Classes d'animation de pet.css : pt-body (le corps qui respire,
// tourne autour de 50 % 92 %), pt-fx (scintillement), pt-z (Zzz), pt-tear (larme, bave). Le skin ajoute pt-led (LED
// qui pulsent) et coupe TOUTES ses animations si l'utilisateur réduit les animations (prefers-reduced-motion).
// Couleur d'humeur (moodColor) : sur les deux anneaux des oreillettes ET les deux LED d'antenne.
//
// ── ACCESSOIRES (architecture prête pour 120+ objets sur 10 emplacements) ─────────────────────────────────────────
// Emplacements (PetSkin.SLOTS) : head (tête), eyes (yeux), neck (cou / torse), hand (main), back (dos), feet (pieds),
// facets (couleur des facettes), effect (effets), decor (décor / fond), pet (petit animal). Un par emplacement.
// Déclarer : PetSkin.defineAccessory({ id, slot, label, draw(ctx) → SVG, palette?, under?, headset? }).
//   • draw(ctx) dessine en coordonnées 200 × 200 à partir des POINTS D'ANCRAGE ctx.a (ci-dessous) ; il renvoie une
//     chaîne SVG, ou { back, front } pour « effect » (derrière / devant Zicou). Jamais de texte saisi par un joueur
//     dans le SVG sans ctx.esc().
//   • slot "facets" : pas de draw, une palette { base: [clair, moyen, sombre], tiles: [couleurs], accents: [[couleur,
//     seuil 0..1], …] } (seuil cumulé : part des facettes de cette couleur).
//   • under: true (tête) : dessiné SOUS l'arceau du casque (casquette, bonnet) ; sinon par-dessus.
//   • headset: { band, cup, ring, sequins } (tête) : remplace les couleurs du casque de Zicou (tenue « casque »).
// Le choix vient de opts.accessories ({ head: "couronne", pet: "chaton", … }) ; opts.outfit (ancien contrat) est un
// accessoire comme un autre, posé sur son emplacement (accessories l'emporte s'ils visent le même emplacement).
// ctx = { a, mood, emotion, stage, variant, ghost, uid, C (couleurs), esc, n (arrondi), bodyClip (clip-path du corps) }.
// Points d'ancrage ctx.a (tous en 200 × 200, recalculés à chaque stade) :
//   ground {x, y}            sol, sous Zicou                    body {x, y, r}       centre et rayon de la boule
//   head {x, y, r}           sommet de la boule (sous l'arceau)  crown {x, y}         dessus de l'arceau (couronne…)
//   eyes {l, r, rx, ry, y}   centre des yeux + taille            mouth {x, y}         bouche
//   neck {x, y, w}           bas de la boule, devant (nœud…)     back {x, y, r}       derrière la boule (ailes, cape)
//   hands {l, r} ({x, y, up}) bout des bras (bébé : bords du corps) feet {l, r, w}     milieu des pieds
//   antennas {l, r}          LED d'antenne                       pet {x, y}           place du petit animal, au sol
//   s                        échelle du corps (1 = adulte, 0.6 = bébé)
// Ordre des calques (du fond vers l'avant) : decor → ombre → effect.back + étincelles « étoile » → [pt-body : back →
// jambes, pieds (feet) → bras → boule (facets) → head « under » → casque → visage → eyes → neck → head → hand] →
// pet → effect.front + signes d'émotion (Zzz, bulle, confettis). Le fantôme ne porte rien (sauf decor).
(function () {
  "use strict";
  const K = 0.5;  // le dessin de base est pensé en 400 × 400 (générateur de la mascotte), affiché en 200 × 200
  const C = { ink: "#1b1030", night: "#15102a", chalk: "#f5f0ff", neon: "#ff4f9a", amber: "#ffb547", cyan: "#5ee7ff",
    violet: "#8f6bff", blush: "#ff7aa8", gold: "#ffd24d", green: "#8be36b", lilac: "#ddd5f7", band: "#1f1650",
    rubber: "#3a2e78", rubberHi: "#6d55f0", cup: "#120d28", halo: "#efe9ff" };
  const MOOD = { egg: "#b9a6ff", happy: C.cyan, party: C.neon, hungry: C.amber, tired: "#8f7bd8", sad: "#7aa2ff",
    sick: C.green, sleep: "#6b5bb8", ghost: "#cfc8ee" };
  const GLOW = { egg: 1, happy: 1, party: 1.25, hungry: 0.8, tired: 0.45, sleep: 0.4, sad: 0.6, sick: 0.55, ghost: 0.3 };
  const DIM = ["tired", "sleep", "sad", "sick"];
  const PALETTES = {
    nuit: { base: ["#5a3fd0", "#2d1d86", "#160d4a"], tiles: ["#b9a6ff", "#8f6bff", "#d9ceff", "#6d55f0"],
      accents: [[C.cyan, 0.12], [C.neon, 0.22], [C.amber, 0.26]] },
    wild: { accents: [[C.neon, 0.3], ["#ff8cc2", 0.45], [C.cyan, 0.5], [C.amber, 0.54]] },
    chrome: { base: ["#f4f6ff", "#9aa3c2", "#3b4058"], tiles: ["#ffffff", "#dfe4f5", "#b9c1dc", "#8f98b8"],
      accents: [[C.cyan, 0.1], ["#ffc4e6", 0.2], [C.amber, 0.24]] },
    ghost: { base: ["#e9e5ff", "#c9c2ea", "#9a94b8"], tiles: ["#ece8ff", "#d6d0f0"], accents: [] },
  };
  // Proportions de Zicou Nuit : rayon de la boule (adulte), longueur des jambes, hauteur des pieds.
  const BODY = { r: 114, legs: 22, k: { baby: 0.6, teen: 0.8 } };
  const SLOTS = Object.freeze(["head", "eyes", "neck", "hand", "back", "feet", "facets", "effect", "decor", "pet"]);
  const ACCESSORIES = new Map();
  let seq = 0;

  // ── Outils ──
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const r1 = (v) => Math.round(v * 10) / 10;
  const n = (v) => r1(v * K);  // 400 → 200
  // Gabarit de chemin : chaque nombre interpolé est une longueur 400 ramenée en 200 (`P\`M${x} ${y}\``).
  const P = (str, ...vals) => str.reduce((acc, s, i) => acc + s + (i < vals.length ? (typeof vals[i] === "number" ? n(vals[i]) : vals[i]) : ""), "");
  // Pseudo-aléatoire stable (mulberry32) : la même boule a toujours les mêmes facettes.
  const rng = (seed) => () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const circle = (x, y, r, fill, stroke, sw, extra) =>
    `<circle cx="${n(x)}" cy="${n(y)}" r="${n(r)}" fill="${fill}"${stroke ? ` stroke="${stroke}" stroke-width="${n(sw)}"` : ""}${extra ? " " + extra : ""}/>`;
  const stroke = (d, color, w, extra) => `<path d="${d}" fill="none" stroke="${color}" stroke-width="${n(w)}" stroke-linecap="round" stroke-linejoin="round"${extra ? " " + extra : ""}/>`;
  const limb = (d, color, w) => stroke(d, C.ink, w + 8) + stroke(d, color, w);
  const sparkle = (x, y, r, color, op, cls) => {
    const q = r * 0.18;
    return `<path${cls ? ` class="${cls}"` : ""} d="${P`M${x} ${y - r} Q${x + q} ${y - q} ${x + r} ${y} Q${x + q} ${y + q} ${x} ${y + r} Q${x - q} ${y + q} ${x - r} ${y} Q${x - q} ${y - q} ${x} ${y - r}`}Z" fill="${color}" opacity="${op ?? 1}"/>`;
  };
  const delay = (i) => `style="animation-delay:${(i % 8) * 0.3}s"`;

  // ── Feuille de style du skin (animations propres + coupure si animations réduites, même hors du panneau) ──
  function injectStyle() {
    if (typeof document === "undefined" || document.getElementById("pt-skin-style")) return;
    const st = document.createElement("style");
    st.id = "pt-skin-style";
    st.textContent = ".pt-svg .pt-led{animation:pt-led 2.2s ease-in-out infinite}"
      + "@keyframes pt-led{0%,100%{opacity:1}50%{opacity:.55}}"
      // Clignement des yeux ouverts (partout où Zicou est dessiné) ; regard : --lx / --ly posés par pet/motion.js.
      + ".pt-svg .pt-eyes{transform-box:fill-box;transform-origin:50% 55%}"
      + ".pt-e-happy .pt-eyes,.pt-e-hungry .pt-eyes,.pt-e-sad .pt-eyes{animation:pt-blink 5.3s ease-in-out infinite}"
      + ".pt-svg .pt-face{transform:translate(var(--lx,0px),var(--ly,0px));transition:transform .35s cubic-bezier(.2,.8,.2,1)}"
      + "@keyframes pt-blink{0%,93%,100%{transform:scaleY(1)}95.5%{transform:scaleY(.08)}}"
      + "@media (prefers-reduced-motion: reduce){.pt-svg,.pt-svg *{animation:none!important;transition:none!important}}";
    (document.head || document.documentElement).appendChild(st);
  }

  // ── Boule à facettes (projection latitude / longitude, lumière en haut à gauche) ──
  function ball(uid, cx, cy, r, glow, bands, pal, seed, outline, twinkle) {
    const rand = rng(seed), half = Math.PI / 2, out = [];
    const pt = (u, v) => [cx + r * Math.sin(u) * Math.cos(v), cy + r * Math.sin(v)];
    for (let i = 0; i < bands; i += 1) {
      for (let j = 0; j < bands; j += 1) {
        const u0 = -half + i * Math.PI / bands, u1 = u0 + Math.PI / bands;
        const v0 = -half + j * Math.PI / bands, v1 = v0 + Math.PI / bands;
        const raw = [pt(u0, v0), pt(u1, v0), pt(u1, v1), pt(u0, v1)];
        const mx = raw.reduce((a, p) => a + p[0], 0) / 4, my = raw.reduce((a, p) => a + p[1], 0) / 4;
        const pts = raw.map(([px, py]) => [mx + (px - mx) * 0.8, my + (py - my) * 0.8]);
        const nx = (mx - cx) / r, ny = (my - cy) / r, nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
        const light = Math.max(0.12, -0.45 * nx - 0.55 * ny + 0.7 * nz);
        const roll = rand(), pick = rand();
        const accent = pal.accents.find(([, p]) => roll < p);
        const col = accent ? accent[0] : pal.tiles[Math.floor(pick * pal.tiles.length)];
        const tw = twinkle && accent && rand() > 0.45 ? ` class="pt-fx" ${delay(i * bands + j)}` : "";
        out.push(`<path d="M${pts.map(([px, py]) => `${n(px)} ${n(py)}`).join(" L")}Z" fill="${col}" opacity="${r1(Math.min(1, light * glow))}"${tw}/>`);
      }
    }
    return `<radialGradient id="${uid}g" cx=".38" cy=".32" r=".75"><stop offset="0" stop-color="${pal.base[0]}"/><stop offset=".6" stop-color="${pal.base[1]}"/><stop offset="1" stop-color="${pal.base[2]}"/></radialGradient>`
      + `<radialGradient id="${uid}s" cx=".4" cy=".35" r=".7"><stop offset=".55" stop-color="#0b0624" stop-opacity="0"/><stop offset="1" stop-color="#0b0624" stop-opacity=".65"/></radialGradient>`
      + `<clipPath id="${uid}c"><circle cx="${n(cx)}" cy="${n(cy)}" r="${n(r)}"/></clipPath>`
      + circle(cx, cy, r, `url(#${uid}g)`) + `<g clip-path="url(#${uid}c)">${out.join("")}`
      + circle(cx, cy, r, `url(#${uid}s)`)
      + `<ellipse cx="${n(cx - r * 0.38)}" cy="${n(cy - r * 0.45)}" rx="${n(r * 0.26)}" ry="${n(r * 0.15)}" fill="#fff" opacity="${r1(0.35 * glow)}" transform="rotate(-30 ${n(cx - r * 0.38)} ${n(cy - r * 0.45)})"/></g>`
      + (outline ? circle(cx, cy, r, "none", C.ink, outline) : "")
      + (glow > 0.6 && r > 40 ? sparkle(cx - r * 0.42, cy - r * 0.5, r * 0.2, "#fff", 0.95, "pt-fx") : "");
  }

  // ── Géométrie selon le stade (bébé : grosse tête sans jambes ; ado : intermédiaire) ──
  function geometry(stage, ghost) {
    const r = BODY.r * (BODY.k[stage] || 1);
    const legs = stage === "baby" ? 0 : BODY.legs * (stage === "teen" ? 0.55 : 1);
    const shoeH = stage === "baby" ? 18 : 24;
    return { cx: 200, cy: 372 - shoeH - legs - r + 8 - (ghost ? 30 : 0), r };
  }

  // ── Visage ──
  function eye(x, y, s, kind) {
    const sw = 3.5 * s;
    if (kind === "open" || kind === "plead") {
      const py = y + 2 * s, pr = (kind === "plead" ? 9 : 7) * s;
      return `<ellipse cx="${n(x)}" cy="${n(y)}" rx="${n(13 * s)}" ry="${n(15 * s)}" fill="#fff" stroke="${C.ink}" stroke-width="${n(sw)}"/>`
        + circle(x, py, pr, C.ink) + circle(x - 3 * s, py - 4 * s, 3 * s, "#fff")
        + (kind === "plead" ? circle(x + 3 * s, py + 3 * s, 1.6 * s, "#fff") : "");
    }
    if (kind === "happy") return stroke(P`M${x - 11 * s} ${y + 4 * s} Q${x} ${y - 13 * s} ${x + 11 * s} ${y + 4 * s}`, C.ink, 5 * s);
    if (kind === "sleep") return stroke(P`M${x - 11 * s} ${y} Q${x} ${y + 10 * s} ${x + 11 * s} ${y}`, C.ink, 5 * s);
    if (kind === "tired") {
      return `<path d="${P`M${x - 13 * s} ${y} A${13 * s} ${15 * s} 0 0 0 ${x + 13 * s} ${y}`}Z" fill="#fff" stroke="${C.ink}" stroke-width="${n(sw)}" stroke-linejoin="round"/>`
        + `<path d="${P`M${x - 5.5 * s} ${y} A${5.5 * s} ${5.5 * s} 0 0 0 ${x + 5.5 * s} ${y}`}Z" fill="${C.ink}"/>`
        + stroke(P`M${x - 15 * s} ${y - s} L${x + 15 * s} ${y + 1.5 * s}`, C.ink, 5 * s);
    }
    if (kind === "spiral") {
      const d = P`M${x} ${y} m${-1.5 * s} 0 a${1.5 * s} ${1.5 * s} 0 1 1 ${3 * s} 0 a${4.5 * s} ${4.5 * s} 0 1 1 ${-9 * s} 0 a${7.5 * s} ${7.5 * s} 0 1 1 ${15 * s} 0`;
      return stroke(d, C.ink, 3 * s);
    }
    const d = 7 * s;  // "x" : fantôme
    return stroke(P`M${x - d} ${y - d} L${x + d} ${y + d} M${x + d} ${y - d} L${x - d} ${y + d}`, C.ink, 4.5 * s, 'opacity=".75"');
  }

  function brows(cx, ey, gap, s, emotion) {
    if (!["happy", "party", "hungry", "sad", "sick", "tired"].includes(emotion)) return "";
    const y = ey - 25 * s;
    return [-1, 1].map((d) => {
      const xi = cx + d * (gap - 11 * s), xo = cx + d * (gap + 11 * s), xm = (xi + xo) / 2;
      if (emotion === "happy" || emotion === "party") {
        const lift = emotion === "party" ? 9 : 6;
        return stroke(P`M${xi} ${y} Q${xm} ${y - lift * s} ${xo} ${y + s}`, C.ink, 4.5 * s);
      }
      if (emotion === "hungry" || emotion === "sad") return stroke(P`M${xi} ${y - 5 * s} Q${xm} ${y - 3 * s} ${xo} ${y + 3 * s}`, C.ink, 4.5 * s);
      return stroke(P`M${xi} ${y + 4 * s} L${xo} ${y + 4 * s}`, C.ink, 4.5 * s);
    }).join("");
  }

  // Bouche cerclée d'un liseré clair (lisible sur les facettes sombres).
  function mouth(x, y, s, kind) {
    const halo = (d, w) => stroke(d, C.halo, w + 7 * s) + stroke(d, C.ink, w);
    if (kind === "smile") return halo(P`M${x - 13 * s} ${y} Q${x} ${y + 13 * s} ${x + 13 * s} ${y}`, 5 * s);
    if (kind === "wavy") return halo(P`M${x - 12 * s} ${y + 2 * s} q${6 * s} ${-5 * s} ${12 * s} 0 t${12 * s} 0`, 4.5 * s);
    if (kind === "frown") return halo(P`M${x - 12 * s} ${y + 8 * s} Q${x} ${y - 4 * s} ${x + 12 * s} ${y + 8 * s}`, 4.5 * s);
    if (kind === "grin") {
      const d = P`M${x - 18 * s} ${y} Q${x} ${y + 32 * s} ${x + 18 * s} ${y}` + "Z";
      return `<path d="${d}" fill="${C.halo}" stroke="${C.halo}" stroke-width="${n(11 * s)}" stroke-linejoin="round"/>`
        + `<path d="${d}" fill="${C.ink}" stroke="${C.ink}" stroke-width="${n(4 * s)}" stroke-linejoin="round"/>`
        + `<ellipse cx="${n(x)}" cy="${n(y + 10 * s)}" rx="${n(7 * s)}" ry="${n(4 * s)}" fill="${C.blush}"/>`;
    }
    const ry = kind === "small" ? 6 : 9, rx = kind === "small" ? 5 : 7, oy = kind === "small" ? 3 : 4;  // "o" / "small"
    return `<ellipse cx="${n(x)}" cy="${n(y + oy * s)}" rx="${n((rx + 3.5) * s)}" ry="${n((ry + 3.5) * s)}" fill="${C.halo}"/>`
      + `<ellipse cx="${n(x)}" cy="${n(y + oy * s)}" rx="${n(rx * s)}" ry="${n(ry * s)}" fill="${C.ink}"/>`;
  }

  function face(cx, ey, gap, s, emotion) {
    const kind = { happy: "open", party: "happy", hungry: "plead", tired: "tired", sleep: "sleep", sad: "open", sick: "spiral", ghost: "x" }[emotion] || "open";
    // pt-eyes (clignement) et pt-face (regard qui suit le doigt) : animés par pet/motion.css, jamais par le skin.
    let out = `<g class="pt-eyes">${eye(cx - gap, ey, s, kind) + eye(cx + gap, ey, s, kind)}</g>` + brows(cx, ey, gap, s, emotion);
    if (["happy", "party", "hungry"].includes(emotion)) {
      out += [-1, 1].map((d) => `<ellipse cx="${n(cx + d * (gap + 12 * s))}" cy="${n(ey + 20 * s)}" rx="${n(8 * s)}" ry="${n(5 * s)}" fill="${C.blush}" opacity=".65"/>`).join("");
    }
    const my = ey + 30 * s;
    const mk = { happy: "smile", party: "grin", hungry: "o", tired: "wavy", sick: "wavy", ghost: "wavy", sleep: "small", sad: "frown" }[emotion] || "smile";
    out += mouth(cx, my, s, mk);
    if (emotion === "sad") {  // larme qui coule
      out += `<path class="pt-tear" d="${P`M${cx + gap + 8 * s} ${ey + 14 * s} q${5 * s} ${10 * s} 0 ${14 * s} q${-5 * s} ${-4 * s} 0 ${-14 * s}`}" fill="${C.cyan}" stroke="${C.ink}" stroke-width="1"/>`;
    }
    if (emotion === "hungry") {  // bave
      out += `<path class="pt-tear" d="${P`M${cx + 8 * s} ${my + 10 * s} q${3 * s} ${7 * s} 0 ${10 * s} q${-3 * s} ${-3 * s} 0 ${-10 * s}`}" fill="${C.cyan}"/>`;
    }
    return `<g class="pt-face">${out}</g>`;
  }

  // ── Casque fin + deux antennes à LED (look = couleurs ; la tenue « casque » le remplace par une version dorée) ──
  function headset(uid, cx, cy, r, mood, dim, ghost, look) {
    const band = ghost ? "#9a94b8" : look.band, cupFill = ghost ? "#9a94b8" : look.cup;
    const ringOp = dim ? 0.45 : 1, glow = ghost ? "" : `filter="url(#${uid}glow)"`;
    const y0 = cy - r * 0.08, w = r * (look.thick || 0.14);
    const arc = P`M${cx - r * 0.98} ${y0} C${cx - r} ${cy - r * 1.28} ${cx + r} ${cy - r * 1.28} ${cx + r * 0.98} ${y0}`;
    let out = stroke(arc, C.ink, w + 9) + stroke(arc, band, w);
    if (look.sequins && !ghost) {
      out += [0.12, 0.26, 0.4, 0.5, 0.6, 0.74, 0.88].map((t, i) => {
        const x = cx + (t - 0.5) * 2 * r * 0.98, y = cy - r * 0.98 + Math.pow((t - 0.5) * 2, 2) * r * 0.86;
        return circle(x, y, w * 0.18, ["#fff", C.neon, C.cyan][i % 3], null, 0, `class="pt-fx" ${delay(i)}`);
      }).join("");
    }
    const cw = r * 0.42, ch = r * 0.78;
    [-1, 1].forEach((d) => {
      const x = cx + d * r * 1.04, tx = cx + d * r * 0.92, ty = cy - r * 1.42;
      out += stroke(P`M${x} ${cy - ch / 2} L${tx} ${ty}`, C.ink, 9) + stroke(P`M${x} ${cy - ch / 2} L${tx} ${ty}`, ghost ? band : (look.stem || C.lilac), 3.5)
        + circle(tx, ty, r * 0.1, C.ink)
        + circle(tx, ty, r * 0.075, mood, null, 0, `class="pt-led" opacity="${ringOp}" ${glow}`);
      out += `<rect x="${n(x - cw / 2)}" y="${n(cy - ch / 2)}" width="${n(cw)}" height="${n(ch)}" rx="${n(cw * 0.45)}" fill="${cupFill}" stroke="${C.ink}" stroke-width="${n(5)}"/>`;
      if (look.sequins && !ghost) out += circle(x - cw * 0.18, cy - ch * 0.3, cw * 0.1, "#fff", null, 0, 'opacity=".8"');
      out += circle(x, cy, r * 0.15, C.cup) + circle(x, cy, r * 0.15, "none", mood, r > 70 ? 6 : 4, `class="pt-led" opacity="${ringOp}" ${glow}`);
    });
    return out;
  }

  // ── Pieds caoutchouc ──
  function shoes(cx, stage) {
    if (stage === "baby") {
      return [-1, 1].map((d) => `<ellipse cx="${n(cx + d * 30)}" cy="${n(364)}" rx="${n(20)}" ry="${n(10)}" fill="${C.rubber}" stroke="${C.ink}" stroke-width="${n(4)}"/>`).join("");
    }
    return [-1, 1].map((d) => {
      const x = cx + d * 30;
      return `<rect x="${n(x - 26)}" y="${n(348)}" width="${n(52)}" height="${n(24)}" rx="${n(12)}" fill="${C.rubber}" stroke="${C.ink}" stroke-width="${n(4)}"/>`
        + `<rect x="${n(x - 18)}" y="${n(352)}" width="${n(20)}" height="${n(6)}" rx="${n(3)}" fill="${C.rubberHi}"/>`;
    }).join("");
  }

  function armsFor(cx, cy, r, emotion, stage) {
    const hands = {};
    if (stage === "baby" || emotion === "ghost") {
      [-1, 1].forEach((d) => { hands[d < 0 ? "l" : "r"] = { x: cx + d * r * 0.95, y: cy + r * 0.35, up: false }; });
      return { svg: "", hands };
    }
    const w = stage === "adult" ? 12 : 10;
    const hero = emotion === "happy" && stage === "adult";
    const svg = [-1, 1].map((d) => {
      const x0 = cx + d * r * 0.78, y0 = cy + r * 0.5;
      const up = emotion === "party" || (hero && d === 1);
      const low = DIM.includes(emotion);
      const x1 = cx + d * (up ? r + 34 : low ? r + 8 : r + 26), y1 = up ? cy - r * 0.55 : low ? cy + r * 1.15 : cy + r;
      hands[d < 0 ? "l" : "r"] = { x: x1, y: y1, up };
      return limb(P`M${x0} ${y0} Q${cx + d * (r + 26)} ${(y0 + y1) / 2 + 10} ${x1} ${y1}`, C.lilac, w)
        + circle(x1, y1, w * 0.8, C.lilac, C.ink, 4);
    }).join("");
    return { svg, hands };
  }

  function ghostTail(cx, cy, r) {
    let d = P`M${cx - r} ${cy} L${cx - r} ${cy + r * 1.3}`;
    for (let i = 0; i < 5; i += 1) {
      const x0 = cx - r + 2 * r * i / 5;
      d += P` Q${x0 + r / 5} ${cy + r * (i % 2 === 0 ? 1.05 : 1.5)} ${x0 + 2 * r / 5} ${cy + r * 1.3}`;
    }
    d += P` L${cx + r} ${cy} Z`;
    return `<path d="${d}" fill="#e6e0ff" opacity=".55" stroke="${C.ink}" stroke-width="${n(4)}" stroke-linejoin="round"/>`;
  }

  // ── Signes d'émotion autour de Zicou ──
  function confetti(cx, cy, r) {
    const rand = rng(81), colors = [C.neon, C.amber, C.cyan, C.violet, "#3ddc97", C.chalk];
    let out = "";
    for (let i = 0; i < 30; i += 1) {
      const x = 20 + rand() * 360, y = 10 + rand() * 190, c = colors[Math.floor(rand() * colors.length)], kind = rand(), rot = r1(rand() * 180);
      if (x > cx - r - 30 && x < cx + r + 30 && y > cy - r - 40) continue;
      const fx = `class="pt-fx" ${delay(i)}`;
      if (kind < 0.5) out += `<rect ${fx} x="${n(x - 5)}" y="${n(y - 2.5)}" width="${n(10)}" height="${n(5)}" rx="${n(1.5)}" fill="${c}" transform="rotate(${rot} ${n(x)} ${n(y)})"/>`;
      else if (kind < 0.75) out += circle(x, y, 3.5, c, null, 0, fx);
      else out += stroke(P`M${x - 8} ${y} q${4} ${-6} ${8} 0 t${8} 0`, c, 3, `${fx} transform="rotate(${rot} ${n(x)} ${n(y)})"`);
    }
    return out;
  }

  function zzz(x, y) {
    return `<g class="pt-z">${[0.7, 1, 1.35].map((k, i) => {
      const w = 14 * k, zx = x + i * 20, zy = y - i * 24;
      return stroke(P`M${zx} ${zy} h${w} l${-w} ${w * 1.1} h${w}`, C.chalk, 4.5);
    }).join("")}</g>`;
  }

  function thoughtPizza(x, y) {
    const t = `translate(${n(x)} ${n(y)}) scale(${r1(1.2 * K * 10) / 10})`;
    return circle(x - 44, y + 48, 6, C.chalk, C.ink, 3) + circle(x - 30, y + 34, 9, C.chalk, C.ink, 3) + circle(x, y, 30, C.chalk, C.ink, 4)
      + `<g transform="${t}"><path d="M-16 -12 Q0 -20 16 -12 L0 18 Z" fill="#ffd36b" stroke="${C.ink}" stroke-width="3" stroke-linejoin="round"/>`
      + `<path d="M-16 -12 Q0 -20 16 -12" fill="none" stroke="#e08a3a" stroke-width="5" stroke-linecap="round"/>`
      + `<circle cx="-4" cy="-3" r="3.4" fill="#ff5a5a"/><circle cx="5" cy="3" r="3" fill="#ff5a5a"/><circle cx="0" cy="10" r="2.4" fill="#ff5a5a"/></g>`;
  }

  function emotionSigns(uid, emotion, cx, cy, r) {
    let out = "";
    if (emotion === "party") {
      out += confetti(cx, cy, r);
      [28, 48].forEach((rr, i) => [-1, 1].forEach((d) => {
        const x0 = cx + d * (r + 30);
        out += stroke(P`M${x0 + d * (rr - 22)} ${cy - rr * 0.8} Q${x0 + d * rr} ${cy} ${x0 + d * (rr - 22)} ${cy + rr * 0.8}`, [C.neon, C.amber][i], 6, `class="pt-fx" filter="url(#${uid}glow)"`);
      }));
    }
    if (emotion === "hungry") out += thoughtPizza(Math.min(340, cx + r + 40), Math.max(66, cy - r - 30));
    if (emotion === "sleep") out += zzz(Math.min(300, cx + r * 0.75), Math.max(92, cy - r * 1.15));
    if (emotion === "sick") {
      out += `<g transform="translate(${n(cx + r * 0.55)} ${n(cy + r * 0.38)}) rotate(35)"><rect x="${n(-4)}" y="0" width="${n(8)}" height="${n(34)}" rx="${n(4)}" fill="#fff" stroke="${C.ink}" stroke-width="${n(3)}"/>`
        + `<circle cx="0" cy="${n(36)}" r="${n(7)}" fill="#ff6b6b" stroke="${C.ink}" stroke-width="${n(3)}"/></g>`;
      out += sparkle(cx - r * 0.6, cy - r * 1.2, 8, C.green, 1, "pt-fx") + sparkle(cx + r * 0.2, cy - r * 1.35, 8, C.green, 1, "pt-fx");
    }
    return out;
  }

  // ── Points d'ancrage (en 200 × 200) pour les accessoires ──
  function anchors(geo, stage, hands, s, gap, ey) {
    const { cx, cy, r } = geo, w = r * 0.14;
    const pt = (x, y, extra) => ({ x: n(x), y: n(y), ...(extra || {}) });
    const feetY = stage === "baby" ? 364 : 360;
    return Object.freeze({
      ground: pt(cx, 378), body: { x: n(cx), y: n(cy), r: n(r) }, head: { x: n(cx), y: n(cy - r), r: n(r) },
      crown: pt(cx, cy - r * 0.98 - w / 2 - 4),
      eyes: { l: pt(cx - gap, ey), r: pt(cx + gap, ey), y: n(ey), rx: n(13 * s), ry: n(15 * s) },
      mouth: pt(cx, ey + 30 * s), neck: { ...pt(cx, cy + r * 0.92), w: n(r * 0.9) }, back: { x: n(cx), y: n(cy), r: n(r) },
      hands: { l: pt(hands.l.x, hands.l.y, { up: hands.l.up }), r: pt(hands.r.x, hands.r.y, { up: hands.r.up }) },
      feet: { l: pt(cx - 30, feetY), r: pt(cx + 30, feetY), w: n(stage === "baby" ? 40 : 52) },
      antennas: { l: pt(cx - r * 0.92, cy - r * 1.42), r: pt(cx + r * 0.92, cy - r * 1.42) },
      pet: pt(Math.min(360, cx + r + 52), 372), s: r1(r / BODY.r),
    });
  }

  // ── Accessoires : registre ──
  function defineAccessory(def) {
    if (!def || typeof def.id !== "string" || !SLOTS.includes(def.slot)) throw new Error("Accessoire invalide : id et slot requis");
    if (def.slot === "facets" ? !def.palette : typeof def.draw !== "function" && !def.headset) throw new Error(`Accessoire ${def.id} : draw ou palette manquant`);
    ACCESSORIES.set(def.id, Object.freeze({ ...def }));
    return def.id;
  }

  // Accessoires portés : la tenue (ancien contrat) puis opts.accessories, un seul par emplacement.
  function equipped(o) {
    const out = {};
    const outfit = o.outfit && ACCESSORIES.get(o.outfit);
    if (outfit) out[outfit.slot] = outfit;
    Object.entries(o.accessories || {}).forEach(([slot, id]) => {
      const acc = id && ACCESSORIES.get(id);
      if (acc && acc.slot === slot) out[slot] = acc;
    });
    return out;
  }

  // Teintures (économie du 4.11.2026) : un accessoire porté prend une couleur de la liste (jamais une couleur libre).
  const DYES = Object.freeze({ rose: "#ff7ab6", or: "#ffc94a", menthe: "#5fe3b4", nuit: "#5b6cff", corail: "#ff7a59" });
  function dyeFilter(uid, color) {
    const hex = DYES[color];
    if (!hex) return "";
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255 * 1.35);
    const row = (k) => `${r1(0.3 * k * 100) / 100} ${r1(0.59 * k * 100) / 100} ${r1(0.11 * k * 100) / 100} 0 0`;
    return `<filter id="${uid}dye-${color}" color-interpolation-filters="sRGB"><feColorMatrix type="matrix" values="${row(r)} ${row(g)} ${row(b)} 0 0 0 1 0"/></filter>`;
  }
  function dyed(svg, acc, ctx) {
    const color = svg && acc && ctx.dyes ? ctx.dyes[acc.id] : "";
    return color && DYES[color] ? `${dyeFilter(ctx.uid, color)}<g filter="url(#${ctx.uid}dye-${color})">${svg}</g>` : svg;
  }

  function drawAcc(acc, ctx, part) {
    if (!acc || typeof acc.draw !== "function") return "";
    try {
      const res = acc.draw(ctx);
      if (res && typeof res === "object") return dyed(res[part || "front"] || "", acc, ctx);
      return part === "back" ? "" : dyed(String(res || ""), acc, ctx);
    } catch (err) {
      if (typeof console !== "undefined") console.warn(`Accessoire ${acc.id} non dessiné`, err);
      return "";
    }
  }

  // ── Œuf facetté avec mini-casque ──
  function egg(uid, emotion, pal) {
    const EGG = "M100 59 C128 59 144 104 144 128 C144 156 125 174 100 174 C75 174 56 156 56 128 C56 104 72 59 100 59 Z";
    const band = "M58 103 C56 31 144 31 142 103";
    const mood = MOOD.egg;
    const cups = [57, 143].map((x) => `<rect x="${x - 8.5}" y="93" width="17" height="32" rx="8" fill="${C.band}" stroke="${C.ink}" stroke-width="2.5"/>`
      + `<circle class="pt-led" cx="${x}" cy="109" r="4.5" fill="${C.cup}" stroke="${mood}" stroke-width="2"/>`).join("");
    return `<ellipse cx="100" cy="180" rx="35" ry="5" fill="#000" opacity=".35"/>`
      + `<g class="pt-body"><path d="M50 110 q-6 5 0 10 M150 110 q6 5 0 10" fill="none" stroke="${C.chalk}" stroke-width="2" stroke-linecap="round" opacity=".6"/>`
      + `<clipPath id="${uid}egg"><path d="${EGG}"/></clipPath><path d="${EGG}" fill="${pal.base[1]}"/>`
      + `<g clip-path="url(#${uid}egg)">${ball(uid, 200, 238, 150, 1, 9, pal, 5, 0, true)}</g>`
      + `<path d="M75 85 Q70 100 71 115" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".45"/>`
      + (emotion === "egg" ? `<path d="M84 98 l7 7 l-5 6 l9 5 l-3 7" fill="none" stroke="${C.ink}" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"/>` : "")
      + `<path d="${EGG}" fill="none" stroke="${C.ink}" stroke-width="3"/>`
      + `<path d="${band}" fill="none" stroke="${C.ink}" stroke-width="11" stroke-linecap="round"/><path d="${band}" fill="none" stroke="${C.band}" stroke-width="6.5" stroke-linecap="round"/>`
      + cups + `</g>`;
  }

  // ── Zicou ──
  function creature(uid, o) {
    const ghost = o.emotion === "ghost" || o.stage === "dead";
    const emotion = ghost ? "ghost" : o.emotion;
    const stage = o.stage === "dead" ? "adult" : o.stage;
    const geo = geometry(stage, ghost), { cx, cy, r } = geo;
    const mood = MOOD[emotion] || C.cyan, dim = DIM.includes(emotion), glow = GLOW[emotion] ?? 1;
    const acc = ghost ? {} : equipped(o);
    const facets = acc.facets?.palette;
    const base = o.shiny ? PALETTES.chrome : PALETTES.nuit;
    let pal = ghost ? PALETTES.ghost : { ...base, ...(facets || {}) };
    if (o.variant === "wild" && !ghost) pal = { ...pal, accents: [...PALETTES.wild.accents, ...pal.accents] };
    const s = r / 100 * (stage === "baby" ? 1.55 : 1.4) * 1.18;  // grands yeux de Zicou Nuit
    const gap = r * 0.36, ey = cy + r * 0.02;
    const arms = armsFor(cx, cy, r, emotion, stage);
    const a = anchors(geo, stage, arms.hands, s, gap, ey);
    const ctx = Object.freeze({ a, mood, emotion, stage, variant: o.variant, ghost, uid, C, esc, n: r1, bodyClip: `url(#${uid}c)`,
      dyes: o.dyes && typeof o.dyes === "object" ? o.dyes : null });

    const head = acc.head;
    const look = head?.headset ? { ...head.headset } : { band: C.band, cup: C.band };
    let hs = headset(uid, cx, cy, r, mood, dim, ghost, look);
    if (o.variant === "wild" && !ghost) hs = `<g transform="rotate(-12 ${n(cx)} ${n(cy)})">${hs}</g>`;

    let body = drawAcc(acc.back, ctx);
    if (ghost) body += ghostTail(cx, cy, r);
    else {
      if (stage !== "baby") body += limb(P`M${cx - 26} ${cy + r - 10} L${cx - 30} ${350}`, C.lilac, 12) + limb(P`M${cx + 26} ${cy + r - 10} L${cx + 30} ${350}`, C.lilac, 12);
      body += shoes(cx, stage) + drawAcc(acc.feet, ctx);
    }
    body += arms.svg;
    body += ball(uid, cx, cy, r, glow, stage === "adult" ? 8 : 6, pal, 21, stage === "baby" ? 5 : 6, !ghost);
    if (o.shiny && !ghost) {
      body += `<linearGradient id="${uid}iri" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffc4e6" stop-opacity=".35"/><stop offset=".5" stop-color="#bff0ff" stop-opacity="0"/><stop offset="1" stop-color="#fff0b8" stop-opacity=".35"/></linearGradient>`
        + circle(cx, cy, r - 3, `url(#${uid}iri)`);
    }
    if (emotion === "sick") body += circle(cx, cy, r - 3, C.green, null, 0, 'opacity=".28"');
    if (head?.under) body += drawAcc(head, ctx);
    body += hs + face(cx, ey, gap, s, emotion) + drawAcc(acc.eyes, ctx) + drawAcc(acc.neck, ctx);
    if (head && !head.under) body += drawAcc(head, ctx);
    body += drawAcc(acc.hand, ctx);
    if (ghost) {
      body = `<g opacity=".85">${body}</g><ellipse class="pt-fx" cx="${n(cx)}" cy="${n(cy - r * 1.32)}" rx="${n(r * 0.5)}" ry="${n(r * 0.12)}" fill="none" stroke="${C.gold}" stroke-width="${n(6)}"/>`;
    }

    const star = o.variant === "star" && !ghost
      ? sparkle(cx - r - 20, cy - r * 0.6, 14, C.gold, 1, "pt-fx") + sparkle(cx + r + 24, cy - r * 0.2, 11, C.gold, 1, "pt-fx") + sparkle(cx + r * 0.8, cy + r + 10, 9, C.gold, 1, "pt-fx")
      : "";
    const shinyFx = o.shiny && !ghost ? sparkle(cx - r - 6, cy + r * 0.3, 9, "#fff", 0.9, "pt-fx") + sparkle(cx + r + 8, cy - r * 0.9, 7, C.cyan, 0.9, "pt-fx") : "";
    return `<g class="pt-l-decor">${drawAcc(acc.decor, ctx)}</g>`
      + `<ellipse cx="${n(200)}" cy="${n(378)}" rx="${n(ghost ? r * 0.5 : r * 0.9)}" ry="${n(10)}" fill="#000" opacity="${ghost ? 0.15 : 0.35}"/>`
      + `<g class="pt-l-aura">${drawAcc(acc.effect, ctx, "back")}${star}${shinyFx}</g>`
      + `<g class="pt-body"${ghost ? ' opacity=".9"' : ""}>${body}</g>`
      + `<g class="pt-l-pet">${drawAcc(acc.pet, ctx)}</g>`
      + `<g class="pt-l-fx">${drawAcc(acc.effect, ctx, "front")}${emotionSigns(uid, emotion, cx, cy, r)}</g>`;
  }

  function render(o) {
    injectStyle();
    const opts = { stage: "baby", variant: "classic", emotion: "happy", outfit: null, label: "", ...(o || {}) };
    seq += 1;
    const uid = `pt${seq}`;
    const glowDef = `<defs><filter id="${uid}glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>`;
    const inner = opts.stage === "egg" ? egg(uid, opts.emotion, opts.shiny ? PALETTES.chrome : PALETTES.nuit) : creature(uid, opts);
    const label = opts.label ? `role="img" aria-label="${esc(opts.label)}"` : 'aria-hidden="true"';
    const cls = `pt-svg pt-${esc(opts.stage)} pt-e-${esc(opts.emotion)}${opts.shiny ? " pt-shiny" : ""}`;
    return `<svg class="${cls}" viewBox="0 0 200 200" ${label} focusable="false">${glowDef}${inner}</svg>`;
  }

  // ── Tenues (app/pet.py OUTFITS) : des accessoires comme les autres, dessinés depuis les points d'ancrage ──
  const OUTFITS = [
    { id: "noeud", slot: "neck", label: "Nœud papillon", draw: ({ a }) => {
      const { x, y } = a.neck, k = a.body.r / 57;
      return `<g transform="translate(${x} ${r1(y + 1)}) scale(${r1(k * 10) / 10})"><path d="M0 0 L-13 -7 L-13 7 Z M0 0 L13 -7 L13 7 Z" fill="${C.neon}" stroke="${C.ink}" stroke-width="2" stroke-linejoin="round"/><circle r="4" fill="${C.amber}" stroke="${C.ink}" stroke-width="2"/></g>`;
    } },
    { id: "lunettes", slot: "eyes", label: "Lunettes de soleil", draw: ({ a }) => {
      const { l, r, rx, ry } = a.eyes, w = rx * 1.45, h = ry * 0.9;
      const lens = (p) => `<rect x="${r1(p.x - w)}" y="${r1(p.y - h)}" width="${r1(w * 2)}" height="${r1(h * 2)}" rx="${r1(h * 0.75)}" fill="#120a26" stroke="${C.ink}" stroke-width="2"/>`
        + `<path d="M${r1(p.x - w * 0.6)} ${r1(p.y - h * 0.45)} h${r1(w * 0.5)}" stroke="${C.cyan}" stroke-width="2" stroke-linecap="round"/>`;
      return lens(l) + lens(r) + `<path d="M${r1(l.x + w)} ${r1(l.y - h * 0.3)} H${r1(r.x - w)}" stroke="${C.ink}" stroke-width="2.5"/>`;
    } },
    { id: "casquette", slot: "head", under: true, label: "Casquette", draw: ({ a }) => {
      const { x, y, r } = a.head;
      return `<path d="M${r1(x - r * 0.74)} ${r1(y + r * 0.42)} Q${x} ${r1(y - r * 0.32)} ${r1(x + r * 0.74)} ${r1(y + r * 0.42)} Z" fill="${C.cyan}" stroke="${C.ink}" stroke-width="2.5" stroke-linejoin="round"/>`
        + `<path d="M${r1(x + r * 0.3)} ${r1(y + r * 0.4)} h${r1(r * 0.78)} q4 0 1.5 4 h${r1(-r * 0.8)} Z" fill="#38bcd8" stroke="${C.ink}" stroke-width="2.5" stroke-linejoin="round"/>`;
    } },
    { id: "casque", slot: "head", label: "Casque de DJ", headset: { band: C.gold, cup: C.gold, stem: "#fff3c4", thick: 0.2, sequins: true } },
    { id: "boa", slot: "neck", label: "Collier lumineux", draw: ({ a }) => {
      const { x, y, r } = a.body;
      return Array.from({ length: 13 }, (_, i) => {
        const t = Math.PI * (0.1 + 0.8 * i / 12), px = x - Math.cos(t) * r * 0.95, py = y + Math.sin(t) * r * 0.9;
        return `<circle class="pt-fx" ${delay(i)} cx="${r1(px)}" cy="${r1(py)}" r="${r1(r * 0.11)}" fill="${[C.cyan, C.neon, C.amber][i % 3]}" stroke="${C.ink}" stroke-width="1.5"/>`;
      }).join("");
    } },
    { id: "chapeau", slot: "head", label: "Chapeau de fête", draw: ({ a }) => {
      const { x, y, r } = a.head, hx = x - r * 0.42, hy = y + r * 0.16, h = r * 0.7;
      return `<g transform="rotate(-18 ${r1(hx)} ${r1(hy)})"><path d="M${r1(hx - h * 0.33)} ${r1(hy)} L${r1(hx)} ${r1(hy - h)} L${r1(hx + h * 0.33)} ${r1(hy)} Z" fill="${C.neon}" stroke="${C.ink}" stroke-width="2.25" stroke-linejoin="round"/>`
        + `<circle cx="${r1(hx - 2.5)}" cy="${r1(hy - h * 0.35)}" r="2" fill="${C.amber}"/><circle cx="${r1(hx + 2)}" cy="${r1(hy - h * 0.6)}" r="2" fill="${C.cyan}"/>`
        + `<circle cx="${r1(hx)}" cy="${r1(hy - h)}" r="4" fill="${C.amber}" stroke="${C.ink}" stroke-width="1.75"/></g>`;
    } },
    { id: "couronne", slot: "head", label: "Couronne", draw: ({ a }) => {
      const { x, y } = a.crown, w = a.body.r * 0.3;
      return `<path d="M${r1(x - w)} ${r1(y)} L${r1(x - w)} ${r1(y - w * 0.9)} L${r1(x - w / 2)} ${r1(y - w * 0.4)} L${x} ${r1(y - w * 1.15)} L${r1(x + w / 2)} ${r1(y - w * 0.4)} L${r1(x + w)} ${r1(y - w * 0.9)} L${r1(x + w)} ${r1(y)} Z" fill="${C.gold}" stroke="${C.ink}" stroke-width="2.25" stroke-linejoin="round"/>`
        + `<circle class="pt-fx" cx="${x}" cy="${r1(y - w * 0.35)}" r="${r1(w * 0.16)}" fill="${C.neon}"/>`;
    } },
    { id: "echarpe", slot: "neck", label: "Écharpe douillette", draw: ({ a }) => {
      const { x, y, r } = a.body, by = y + r * 0.72, w = r * 0.86;
      return `<path d="M${r1(x - w)} ${r1(by - r * 0.08)} Q${x} ${r1(by + r * 0.26)} ${r1(x + w)} ${r1(by - r * 0.08)} L${r1(x + w * 0.92)} ${r1(by + r * 0.14)} Q${x} ${r1(by + r * 0.46)} ${r1(x - w * 0.92)} ${r1(by + r * 0.14)} Z" fill="${C.neon}" stroke="${C.ink}" stroke-width="2" stroke-linejoin="round"/>`
        + `<path d="M${r1(x - w * 0.5)} ${r1(by + r * 0.24)} l-3 ${r1(r * 0.42)} h${r1(r * 0.2)} l1 ${r1(-r * 0.36)} Z" fill="${C.amber}" stroke="${C.ink}" stroke-width="2" stroke-linejoin="round"/>`
        + [-0.5, 0, 0.5].map((t) => `<path d="M${r1(x + t * w)} ${r1(by + r * 0.08 + Math.abs(t) * -r * 0.06)} v${r1(r * 0.16)}" stroke="${C.amber}" stroke-width="2" stroke-linecap="round"/>`).join("");
    } },
    { id: "bonnet", slot: "head", under: true, label: "Bonnet à pompon", draw: ({ a }) => {
      const { x, y, r } = a.head;
      return `<path d="M${r1(x - r * 0.78)} ${r1(y + r * 0.5)} Q${r1(x - r * 0.8)} ${r1(y - r * 0.26)} ${x} ${r1(y - r * 0.28)} Q${r1(x + r * 0.8)} ${r1(y - r * 0.26)} ${r1(x + r * 0.78)} ${r1(y + r * 0.5)} Z" fill="${C.cyan}" stroke="${C.ink}" stroke-width="2.5" stroke-linejoin="round"/>`
        + `<path d="M${r1(x - r * 0.8)} ${r1(y + r * 0.42)} Q${x} ${r1(y + r * 0.2)} ${r1(x + r * 0.8)} ${r1(y + r * 0.42)}" fill="none" stroke="${C.chalk}" stroke-width="${r1(r * 0.14)}" stroke-linecap="round"/>`
        + `<circle cx="${x}" cy="${r1(y - r * 0.3)}" r="${r1(r * 0.16)}" fill="${C.neon}" stroke="${C.ink}" stroke-width="2"/>`;
    } },
    { id: "paillettes", slot: "neck", label: "Veste à paillettes", draw: ({ a, bodyClip }) => {
      const { x, y, r } = a.body;
      let dots = "";
      for (let i = 0; i < 18; i += 1) {
        const px = x - r + (i % 6) * r * 0.4 + (Math.floor(i / 6) % 2) * r * 0.2, py = y + r * 0.45 + Math.floor(i / 6) * r * 0.2;
        dots += `<circle class="pt-fx" ${delay(i)} cx="${r1(px)}" cy="${r1(py)}" r="${r1(r * 0.06)}" fill="${["#fff", C.gold, C.cyan][i % 3]}"/>`;
      }
      return `<g clip-path="${bodyClip}"><path d="M${r1(x - r)} ${r1(y + r * 0.36)} Q${x} ${r1(y + r * 0.62)} ${r1(x + r)} ${r1(y + r * 0.36)} V${r1(y + r)} H${r1(x - r)} Z" fill="${C.neon}" opacity=".92"/>${dots}`
        + `<path d="M${x} ${r1(y + r * 0.5)} V${r1(y + r)}" stroke="${C.ink}" stroke-width="2"/></g>`;
    } },
    { id: "ailes", slot: "back", label: "Ailes de fée", draw: ({ a }) => {
      const { x, y, r } = a.back;
      // Deux paires d'ailes translucides (grande en haut, petite en bas), nervure claire, derrière la boule.
      const wing = (d, x0, y0, x1, y1, x2, y2, fill) => `<path d="M${r1(x + d * x0)} ${r1(y + y0)} Q${r1(x + d * x1)} ${r1(y + y1)} ${r1(x + d * x2)} ${r1(y + y2)} Q${r1(x + d * (x2 - r * 0.1))} ${r1(y + y2 + r * 0.45)} ${r1(x + d * x0)} ${r1(y + y0 + r * 0.25)} Z" fill="${fill}" fill-opacity=".6" stroke="${C.ink}" stroke-width="1.5" stroke-linejoin="round"/>`
        + `<path d="M${r1(x + d * x0)} ${r1(y + y0 + r * 0.1)} Q${r1(x + d * (x1 * 0.8))} ${r1(y + y1 * 0.6)} ${r1(x + d * (x2 - r * 0.15))} ${r1(y + y2 + r * 0.12)}" fill="none" stroke="#fff" stroke-width="1.2" opacity=".7"/>`;
      return `<g class="pt-fx">${[-1, 1].map((d) => wing(d, r * 0.55, -r * 0.35, r * 1.72, -r * 1.3, r * 1.62, -r * 0.3, "#bff0ff")
        + wing(d, r * 0.6, r * 0.15, r * 1.5, r * 0.1, r * 1.3, r * 0.6, "#ffc4e6")).join("")}</g>`;
    } },
    { id: "cape", slot: "back", label: "Cape de héros", draw: ({ a }) => {
      const { x, y, r } = a.back, g = a.ground.y;
      return `<path d="M${r1(x - r * 0.7)} ${r1(y - r * 0.2)} Q${r1(x - r * 1.5)} ${r1(g - 8)} ${r1(x - r * 1.2)} ${r1(g - 4)} L${r1(x + r * 1.2)} ${r1(g - 4)} Q${r1(x + r * 1.5)} ${r1(g - 8)} ${r1(x + r * 0.7)} ${r1(y - r * 0.2)} Z" fill="#e0315f" stroke="${C.ink}" stroke-width="2.5" stroke-linejoin="round"/>`;
    } },
    { id: "aureole", slot: "head", label: "Auréole", draw: ({ a }) => {
      const { x, y } = a.crown;
      return `<ellipse class="pt-fx" cx="${x}" cy="${r1(y - 9)}" rx="${r1(a.body.r * 0.45)}" ry="${r1(a.body.r * 0.11)}" fill="none" stroke="${C.gold}" stroke-width="3"/>`;
    } },
    { id: "comete", slot: "effect", label: "Comète", draw: ({ a, uid }) => {
      const { x, y, r } = a.body, hx = x + r + 14, hy = y - r * 0.9;
      return {
        back: `<linearGradient id="${uid}com" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="${C.cyan}" stop-opacity="0"/><stop offset="1" stop-color="${C.gold}"/></linearGradient>`
          + `<path d="M${r1(x - r - 18)} ${r1(y + r * 0.6)} Q${r1(x - r * 0.4)} ${r1(y - r * 1.5)} ${r1(hx)} ${r1(hy)}" fill="none" stroke="url(#${uid}com)" stroke-width="5" stroke-linecap="round"/>`,
        front: `<path class="pt-fx" transform="translate(${r1(hx)} ${r1(hy)})" d="M0 -8 L2.2 -2.2 L8 0 L2.2 2.2 L0 8 L-2.2 2.2 L-8 0 L-2.2 -2.2 Z" fill="${C.gold}" stroke="${C.ink}" stroke-width="1"/>`,
      };
    } },
  ];
  OUTFITS.forEach(defineAccessory);

  window.PetSkin = Object.freeze({
    id: "zicou-nuit",
    creatureName: "Zicou",
    render,
    moodColor: (emotion) => MOOD[emotion] || C.cyan,
    SLOTS,
    PALETTES: Object.freeze({ ...PALETTES }),
    defineAccessory,
    accessory: (id) => ACCESSORIES.get(id) || null,
    accessories: (slot) => [...ACCESSORIES.values()].filter((acc) => !slot || acc.slot === slot),
    DYES,
  });
})();
