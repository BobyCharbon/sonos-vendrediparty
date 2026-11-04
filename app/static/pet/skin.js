// 🥚 Compagnon — COUCHE GRAPHIQUE (skin), seul fichier à remplacer le jour où l'admin choisit la mascotte.
// Contrat : window.PetSkin = { id, creatureName, render(opts) → chaîne SVG, moodColor(emotion) → couleur CSS }.
//   opts = { stage: "egg"|"baby"|"teen"|"adult"|"dead", variant: "star"|"classic"|"wild",
//            emotion: "egg"|"happy"|"party"|"hungry"|"tired"|"sad"|"sick"|"sleep"|"ghost",
//            outfit: null|"noeud"|"lunettes"|"casquette"|"casque"|"boa"|"chapeau"|"couronne", label: texte VoiceOver }
// Les classes pt-fx (scintillement), pt-z (sommeil) et pt-tear servent aux animations de pet.css (désactivées si
// l'utilisateur réduit les animations). Rien d'autre ne dépend du dessin : un nouveau skin peut tout changer.
//
// Version PROVISOIRE (4.11.2026) : « boule à facettes vivante » (Paillou) avec l'anneau d'humeur d'une petite enceinte
// (Bassou) sur le ventre, en attendant le mélange choisi par l'admin. Dessin 100 % code, sans fichier externe.
(function () {
  "use strict";
  const C = { ink: "#1b1030", violet: "#5a3fd0", deep: "#2d1d86", night: "#160d4a", lav: "#b9a6ff", neon: "#ff4f9a",
    cyan: "#5ee7ff", amber: "#ffb547", silver: "#ddd5f7", gold: "#ffd24d", green: "#8be36b" };
  const MOOD = { egg: C.lav, happy: C.cyan, party: C.neon, hungry: C.amber, tired: "#8f7bd8", sad: "#7aa2ff",
    sick: C.green, sleep: "#6b5bb8", ghost: "#cfc8ee" };
  const SIZE = { baby: 40, teen: 50, adult: 58, dead: 54 };
  const FACET = [C.lav, C.cyan, "#8f6bff", "#d9ceff", C.neon, C.amber];
  let seq = 0;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Pseudo-aléatoire stable : la même boule a toujours les mêmes facettes.
  const rnd = (i) => { const x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); };

  function facets(id, cx, cy, r, variant, dim) {
    const step = r / 3.4, out = [];
    let i = 0;
    for (let y = cy - r; y < cy + r; y += step) {
      for (let x = cx - r; x < cx + r; x += step) {
        i += 1;
        const pick = variant === "wild" ? [C.neon, "#ff8cc2", C.lav, C.amber][i % 4] : FACET[Math.floor(rnd(i) * FACET.length)];
        const op = (0.25 + rnd(i + 99) * 0.6) * (dim ? 0.45 : 1);
        const tw = rnd(i + 7) > 0.82 ? ` class="pt-fx" style="animation-delay:${(rnd(i + 3) * 2.4).toFixed(2)}s"` : "";
        out.push(`<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(step - 2).toFixed(1)}" height="${(step - 2).toFixed(1)}" rx="1.5" fill="${pick}" opacity="${op.toFixed(2)}"${tw}/>`);
      }
    }
    return `<g clip-path="url(#${id}c)">${out.join("")}</g>`;
  }

  function eyes(emotion, cx, ey, gap, s) {
    const L = cx - gap, R = cx + gap, w = 3.2 * s;
    const open = (x) => `<circle cx="${x}" cy="${ey}" r="${7 * s}" fill="#fff" stroke="${C.ink}" stroke-width="${w * 0.8}"/>`
      + `<circle cx="${x + 1.2 * s}" cy="${ey + 0.8 * s}" r="${3.6 * s}" fill="${C.ink}"/><circle cx="${x + 2.4 * s}" cy="${ey - 0.8 * s}" r="${1.3 * s}" fill="#fff"/>`;
    const arc = (x, up) => `<path d="M${x - 6 * s} ${ey} Q${x} ${ey + (up ? -7 : 6) * s} ${x + 6 * s} ${ey}" fill="none" stroke="${C.ink}" stroke-width="${w}" stroke-linecap="round"/>`;
    switch (emotion) {
      case "party": return arc(L, true) + arc(R, true);
      case "sleep": return arc(L, false) + arc(R, false);
      case "tired": return [L, R].map((x) => `<path d="M${x - 6.5 * s} ${ey} h${13 * s}" stroke="${C.ink}" stroke-width="${w}" stroke-linecap="round"/><path d="M${x - 5 * s} ${ey + 1} q${5 * s} ${5 * s} ${10 * s} 0" fill="#fff" stroke="${C.ink}" stroke-width="${w * 0.7}"/>`).join("");
      case "sick": return [L, R].map((x) => `<path d="M${x} ${ey} m-1 0 a1 1 0 1 1 2 0 a3 3 0 1 1 -6 0 a5 5 0 1 1 10 0" transform="scale(1)" fill="none" stroke="${C.ink}" stroke-width="${w * 0.7}" stroke-linecap="round"/>`).join("");
      case "ghost": return [L, R].map((x) => `<path d="M${x - 4 * s} ${ey - 4 * s} l${8 * s} ${8 * s} M${x + 4 * s} ${ey - 4 * s} l${-8 * s} ${8 * s}" stroke="${C.ink}" stroke-width="${w * 0.8}" stroke-linecap="round" opacity=".7"/>`).join("");
      case "sad": return open(L) + open(R) + `<path d="M${L - 7 * s} ${ey - 10 * s} l${10 * s} ${3 * s} M${R + 7 * s} ${ey - 10 * s} l${-10 * s} ${3 * s}" stroke="${C.ink}" stroke-width="${w * 0.8}" stroke-linecap="round"/>`;
      default: return open(L) + open(R);
    }
  }

  function mouth(emotion, cx, my, s) {
    const w = 3.2 * s, st = `fill="none" stroke="${C.ink}" stroke-width="${w}" stroke-linecap="round"`;
    switch (emotion) {
      case "party": return `<path d="M${cx - 9 * s} ${my - 2 * s} Q${cx} ${my + 14 * s} ${cx + 9 * s} ${my - 2 * s} Z" fill="${C.neon}" stroke="${C.ink}" stroke-width="${w * 0.8}" stroke-linejoin="round"/>`;
      case "hungry": return `<ellipse cx="${cx}" cy="${my + 2 * s}" rx="${4 * s}" ry="${5 * s}" fill="${C.ink}"/><path class="pt-tear" d="M${cx + 7 * s} ${my + 2 * s} q${2 * s} ${5 * s} 0 ${7 * s} q${-2 * s} ${-2 * s} 0 ${-7 * s}" fill="${C.cyan}"/>`;
      case "sad": case "sick": return `<path d="M${cx - 7 * s} ${my + 5 * s} Q${cx} ${my - 3 * s} ${cx + 7 * s} ${my + 5 * s}" ${st}/>`;
      case "tired": case "ghost": return `<path d="M${cx - 5 * s} ${my + 2 * s} h${10 * s}" ${st}/>`;
      case "sleep": return `<circle cx="${cx}" cy="${my + 2 * s}" r="${2.6 * s}" fill="${C.ink}"/>`;
      default: return `<path d="M${cx - 9 * s} ${my} Q${cx} ${my + 11 * s} ${cx + 9 * s} ${my}" ${st}/>`;
    }
  }

  function extras(emotion, cx, top, r) {
    switch (emotion) {
      case "sleep": case "tired":
        return `<g class="pt-z" font-family="system-ui,sans-serif" font-weight="800" fill="${C.lav}"><text x="${cx + r * 0.75}" y="${top + 8}" font-size="16">z</text><text x="${cx + r * 0.95}" y="${top - 6}" font-size="12">z</text></g>`;
      case "party":
        return [0, 1, 2, 3, 4, 5, 6, 7].map((i) => {
          const a = (i / 8) * Math.PI * 2, d = r + 18;
          return `<rect class="pt-fx" style="animation-delay:${i * 0.15}s" x="${(cx + Math.cos(a) * d).toFixed(1)}" y="${(top + r + Math.sin(a) * d).toFixed(1)}" width="6" height="10" rx="2" fill="${[C.neon, C.cyan, C.amber, C.lav][i % 4]}" transform="rotate(${i * 37} ${(cx + Math.cos(a) * d).toFixed(1)} ${(top + r + Math.sin(a) * d).toFixed(1)})"/>`;
        }).join("");
      case "hungry":
        return `<g transform="translate(${cx + r * 0.7} ${top - 14})"><rect x="0" y="0" width="34" height="26" rx="13" fill="#fff" opacity=".92"/><text x="17" y="18" font-size="15" text-anchor="middle">🍕</text></g>`;
      case "sick":
        return `<g transform="translate(${cx + r * 0.62} ${top + 4}) rotate(30)"><rect width="5" height="20" rx="2.5" fill="#fff" stroke="${C.ink}" stroke-width="2"/><circle cx="2.5" cy="21" r="4" fill="#ff6b6b" stroke="${C.ink}" stroke-width="2"/></g>`;
      default: return "";
    }
  }

  function outfitSvg(outfit, cx, top, r, ey) {
    const s = r / 50;
    switch (outfit) {
      case "noeud":
        return `<g transform="translate(${cx} ${top + r * 2 - 4})"><path d="M0 0 L-16 -9 L-16 9 Z M0 0 L16 -9 L16 9 Z" fill="${C.neon}" stroke="${C.ink}" stroke-width="3" stroke-linejoin="round"/><circle r="5" fill="${C.amber}" stroke="${C.ink}" stroke-width="3"/></g>`;
      case "lunettes":
        return `<g fill="#120a26" stroke="${C.ink}" stroke-width="3"><rect x="${cx - 26 * s}" y="${ey - 9 * s}" width="${22 * s}" height="${15 * s}" rx="${6 * s}"/><rect x="${cx + 4 * s}" y="${ey - 9 * s}" width="${22 * s}" height="${15 * s}" rx="${6 * s}"/><path d="M${cx - 4 * s} ${ey - 4 * s} h${8 * s}" fill="none"/></g><path d="M${cx - 20 * s} ${ey - 6 * s} l6 0" stroke="${C.cyan}" stroke-width="2.5" stroke-linecap="round"/>`;
      case "casquette":
        return `<g transform="translate(${cx} ${top + 6})"><path d="M${-r * 0.62} 4 Q0 ${-r * 0.55} ${r * 0.62} 4 Z" fill="${C.cyan}" stroke="${C.ink}" stroke-width="3.5" stroke-linejoin="round"/><path d="M${r * 0.3} 3 h${r * 0.62} q6 0 2 5 h${-r * 0.62}" fill="#38bcd8" stroke="${C.ink}" stroke-width="3.5" stroke-linejoin="round"/><circle cy="${-r * 0.24}" r="3.5" fill="${C.neon}"/></g>`;
      case "casque":
        return `<g fill="none" stroke="${C.ink}" stroke-width="10" stroke-linecap="round"><path d="M${cx - r * 0.92} ${top + r} Q${cx - r} ${top - r * 0.2} ${cx} ${top - 6} Q${cx + r} ${top - r * 0.2} ${cx + r * 0.92} ${top + r}"/></g><path d="M${cx - r * 0.92} ${top + r} Q${cx - r} ${top - r * 0.2} ${cx} ${top - 6} Q${cx + r} ${top - r * 0.2} ${cx + r * 0.92} ${top + r}" fill="none" stroke="${C.neon}" stroke-width="5" stroke-linecap="round"/>`
          + [-1, 1].map((d) => `<rect x="${cx + d * r * 0.92 - 9}" y="${top + r - 14}" width="18" height="28" rx="8" fill="${C.neon}" stroke="${C.ink}" stroke-width="3.5"/>`).join("");
      case "boa":
        return Array.from({ length: 9 }, (_, i) => {
          const a = Math.PI * (0.18 + 0.64 * i / 8), x = cx - Math.cos(a) * r * 0.86, y = top + r + Math.sin(a) * r * 0.86;
          return `<circle class="pt-fx" style="animation-delay:${i * 0.12}s" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="5" fill="${[C.cyan, C.neon, C.amber][i % 3]}" stroke="${C.ink}" stroke-width="2"/>`;
        }).join("");
      case "chapeau":
        return `<g transform="translate(${cx + r * 0.25} ${top + 4}) rotate(14)"><path d="M-17 0 L0 -40 L17 0 Z" fill="${C.neon}" stroke="${C.ink}" stroke-width="3.5" stroke-linejoin="round"/><circle cx="-5" cy="-12" r="2.6" fill="${C.amber}"/><circle cx="5" cy="-22" r="2.6" fill="${C.cyan}"/><circle cy="-42" r="6" fill="${C.amber}" stroke="${C.ink}" stroke-width="3"/></g>`;
      case "couronne":
        return `<g transform="translate(${cx} ${top + 2})"><path d="M-22 0 L-22 -20 L-11 -9 L0 -26 L11 -9 L22 -20 L22 0 Z" fill="${C.gold}" stroke="${C.ink}" stroke-width="3.5" stroke-linejoin="round"/><circle cy="-8" r="3.5" fill="${C.neon}"/></g>`;
      default: return "";
    }
  }

  function egg(id, emotion) {
    const cracked = emotion === "egg";
    let tiles = "";
    for (let i = 0; i < 42; i += 1) {   // 7 × 6 tuiles, découpées par la forme de l'œuf
      const x = 55 + (i % 7) * 13, y = 96 + Math.floor(i / 7) * 13;
      tiles += `<rect x="${x}" y="${y}" width="11" height="11" rx="2" fill="${FACET[i % FACET.length]}" opacity="${(0.35 + rnd(i) * 0.5).toFixed(2)}"/>`;
    }
    return `<defs><clipPath id="${id}c"><ellipse cx="100" cy="118" rx="46" ry="58"/></clipPath>
      <radialGradient id="${id}e" cx=".38" cy=".3" r=".8"><stop offset="0" stop-color="#fff"/><stop offset=".7" stop-color="${C.silver}"/><stop offset="1" stop-color="${C.lav}"/></radialGradient></defs>
      <ellipse cx="100" cy="186" rx="44" ry="8" fill="#000" opacity=".3"/>
      <g class="pt-body"><ellipse cx="100" cy="118" rx="46" ry="58" fill="url(#${id}e)" stroke="${C.ink}" stroke-width="5"/>
      <g clip-path="url(#${id}c)">${tiles}</g>
      ${cracked ? `<path d="M70 92 l10 8 l8 -9 l9 9 l9 -8 l10 9" fill="none" stroke="${C.ink}" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round"/>` : ""}
      <path d="M78 82 q6 -10 16 -12" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".8"/></g>`;
  }

  function creature(id, o) {
    const stage = o.stage === "dead" ? "adult" : o.stage, ghost = o.emotion === "ghost";
    const r = SIZE[o.stage] || SIZE.adult, cx = 100, cy = 182 - r - (stage === "baby" ? 12 : 26), top = cy - r;
    const s = r / 50, ey = cy - r * 0.12, my = cy + r * 0.2, mood = MOOD[o.emotion] || C.cyan;
    const dim = ["sleep", "tired", "sad", "sick"].includes(o.emotion);
    const body = o.emotion === "sick" ? `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${C.green}" opacity=".22"/>` : "";
    const arms = stage === "baby" ? "" : [-1, 1].map((d) => {
      const up = o.emotion === "party" || (d === 1 && o.emotion === "happy" && stage === "adult");
      const x0 = cx + d * r * 0.92, y0 = cy + r * 0.15, x1 = cx + d * (r + 20), y1 = up ? cy - r * 0.75 : cy + r * 0.62;
      return `<path d="M${x0} ${y0} Q${cx + d * (r + 16)} ${(y0 + y1) / 2} ${x1} ${y1}" fill="none" stroke="${C.ink}" stroke-width="11" stroke-linecap="round"/><path d="M${x0} ${y0} Q${cx + d * (r + 16)} ${(y0 + y1) / 2} ${x1} ${y1}" fill="none" stroke="${C.silver}" stroke-width="5" stroke-linecap="round"/><circle cx="${x1}" cy="${y1}" r="5.5" fill="${C.silver}" stroke="${C.ink}" stroke-width="3"/>`;
    }).join("");
    const legs = stage === "adult"
      ? [-1, 1].map((d) => `<path d="M${cx + d * 14} ${cy + r - 4} v20" stroke="${C.ink}" stroke-width="8" stroke-linecap="round"/><rect x="${cx + d * 14 - 12}" y="${cy + r + 14}" width="24" height="12" rx="5" fill="${C.neon}" stroke="${C.ink}" stroke-width="3.5"/><rect x="${cx + d * 14 - 12}" y="${cy + r + 22}" width="24" height="5" rx="2" fill="${C.amber}"/>`).join("")
      : [-1, 1].map((d) => `<ellipse cx="${cx + d * r * 0.42}" cy="${cy + r + 4}" rx="${10 * s + 3}" ry="6" fill="${C.neon}" stroke="${C.ink}" stroke-width="3.5"/>`).join("");
    const hookBend = o.variant === "wild" ? `transform="rotate(-24 ${cx} ${top})"` : "";
    const hook = `<g ${hookBend}><path d="M${cx} ${top + 4} v-14" stroke="${C.ink}" stroke-width="8" stroke-linecap="round"/><path d="M${cx} ${top + 4} v-14" stroke="${C.silver}" stroke-width="3" stroke-linecap="round"/><circle cx="${cx}" cy="${top - 16}" r="6" fill="none" stroke="${C.ink}" stroke-width="7"/><circle cx="${cx}" cy="${top - 16}" r="6" fill="none" stroke="${C.silver}" stroke-width="2.5"/></g>`;
    const halo = o.variant === "star" && !ghost
      ? [0, 1, 2].map((i) => `<path class="pt-fx" style="animation-delay:${i * 0.5}s" transform="translate(${[38, 162, 150][i]} ${[62, 74, 150][i]})" d="M0 -9 L2.5 -2.5 L9 0 L2.5 2.5 L0 9 L-2.5 2.5 L-9 0 L-2.5 -2.5 Z" fill="${C.gold}"/>`).join("") : "";
    const ring = `<circle cx="${cx}" cy="${cy + r * 0.62}" r="${r * 0.2}" fill="${C.night}" stroke="${mood}" stroke-width="${4 * s + 1}"/><circle cx="${cx}" cy="${cy + r * 0.62}" r="${r * 0.08}" fill="${mood}" opacity=".8"/>`;
    const face = `<ellipse cx="${cx}" cy="${cy + r * 0.02}" rx="${r * 0.62}" ry="${r * 0.42}" fill="${C.night}" opacity=".5"/>`;
    return `<defs><clipPath id="${id}c"><circle cx="${cx}" cy="${cy}" r="${r}"/></clipPath>
      <radialGradient id="${id}b" cx=".38" cy=".32" r=".75"><stop offset="0" stop-color="${C.violet}"/><stop offset=".6" stop-color="${C.deep}"/><stop offset="1" stop-color="${C.night}"/></radialGradient>
      <radialGradient id="${id}s" cx=".4" cy=".35" r=".7"><stop offset=".55" stop-color="#0b0624" stop-opacity="0"/><stop offset="1" stop-color="#0b0624" stop-opacity=".7"/></radialGradient></defs>
      <ellipse cx="${cx}" cy="186" rx="${r * 0.9}" ry="8" fill="#000" opacity="${ghost ? 0.12 : 0.32}"/>
      ${halo}
      <g class="pt-body" ${ghost ? 'opacity=".55"' : ""}>${legs}${arms}${hook}
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#${id}b)"/>${facets(id, cx, cy, r, o.variant, dim || ghost)}
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#${id}s)"/>${body}
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${C.ink}" stroke-width="5"/>
        ${ghost ? "" : `<path class="pt-fx" d="M${cx - r * 0.45} ${cy - r * 0.62} l4 -10 l4 10 l10 4 l-10 4 l-4 10 l-4 -10 l-10 -4 Z" fill="#fff" opacity=".9"/>`}
        ${face}${ring}${eyes(o.emotion, cx, ey, r * 0.3, s)}${mouth(o.emotion, cx, my - r * 0.1, s)}
        ${["happy", "party"].includes(o.emotion) ? [-1, 1].map((d) => `<ellipse cx="${cx + d * r * 0.46}" cy="${ey + 11 * s}" rx="${6 * s}" ry="${3.6 * s}" fill="${C.neon}" opacity=".45"/>`).join("") : ""}
        ${ghost ? "" : outfitSvg(o.outfit, cx, top, r, ey)}</g>
      ${extras(o.emotion, cx, top, r)}`;
  }

  function render(o) {
    const opts = { stage: "baby", variant: "classic", emotion: "happy", outfit: null, label: "", ...(o || {}) };
    seq += 1;
    const id = `pt${seq}`;
    const inner = opts.stage === "egg" ? egg(id, opts.emotion) : creature(id, opts);
    const label = opts.label ? `role="img" aria-label="${esc(opts.label)}"` : 'aria-hidden="true"';
    return `<svg class="pt-svg pt-${esc(opts.stage)} pt-e-${esc(opts.emotion)}" viewBox="0 0 200 200" ${label} focusable="false">${inner}</svg>`;
  }

  window.PetSkin = Object.freeze({
    id: "paillou-bassou-provisoire",
    creatureName: "Paillou",
    render,
    moodColor: (emotion) => MOOD[emotion] || C.cyan,
  });
})();
