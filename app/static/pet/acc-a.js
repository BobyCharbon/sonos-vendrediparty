// 🪩 Compagnon — accessoires de la collection (lot A), 1/2 : tête, yeux, cou, main. Chaque objet du catalogue
// (app/pet_catalog.json) est dessiné ici ou dans acc-b.js, sur Zicou Nuit, par le contrat de skin.js
// (PetSkin.defineAccessory). GABARIT PAR EMPLACEMENT : un objet est dessiné une fois, en coordonnées « adulte » autour
// d'un point d'ancrage, puis posé et mis à l'échelle (k = rayon de la boule / 57) : il tient sur tous les stades.
// Les 14 tenues d'avant la collection restent dans skin.js (même identifiant). Jamais de texte de joueur ici.
(function () {
  "use strict";
  const S = window.PetSkin;
  if (!S) return;
  const INK = "#1b1030";
  const r1 = (v) => Math.round(v * 10) / 10;
  const k = (a) => r1(a.body.r / 57 * 100) / 100;   // 1 = adulte
  const at = (x, y, kk, inner, rot) => `<g transform="translate(${r1(x)} ${r1(y)})${rot ? ` rotate(${rot})` : ""} scale(${kk})">${inner}</g>`;
  const line = (d, c, w, extra) => `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"${extra ? " " + extra : ""}/>`;
  const shape = (d, fill, sw, extra) => `<path d="${d}" fill="${fill}" stroke="${INK}" stroke-width="${sw ?? 1.6}" stroke-linejoin="round"${extra ? " " + extra : ""}/>`;
  const dot = (x, y, r, fill, extra) => `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}"${extra ? " " + extra : ""}/>`;
  const fx = (i) => `class="pt-fx" style="animation-delay:${(i % 8) * 0.3}s"`;
  const def = (id, slot, draw, more) => S.defineAccessory({ id, slot, label: id, draw, ...(more || {}) });

  // ── Gabarits ──
  // Tête « dessus » : au-dessus de l'arceau du casque (couronne, chapeau). Origine = a.crown.
  const onTop = (inner) => ({ a }) => at(a.crown.x, a.crown.y, k(a), inner);
  // Tête « dessous » : posé sur le haut de la boule, sous l'arceau (bandeau, casque de grimpe). Origine = sommet.
  const onHead = (inner) => ({ a }) => at(a.head.x, a.head.y, k(a), inner);
  // Yeux : une forme par œil, centrée sur l'œil, plus un pont. La forme reçoit le côté (-1 gauche, 1 droite).
  const glasses = (lens, bridge) => ({ a }) => {
    const kk = r1(a.eyes.rx / 9.3 * 100) / 100;
    return at(a.eyes.l.x, a.eyes.l.y, kk, lens(-1)) + at(a.eyes.r.x, a.eyes.r.y, kk, lens(1))
      + (bridge ? line(`M${r1(a.eyes.l.x + a.eyes.rx * 1.2)} ${r1(a.eyes.y - a.eyes.ry * 0.25)} H${r1(a.eyes.r.x - a.eyes.rx * 1.2)}`, bridge, 2) : "");
  };
  // Cou : sous la bouche, devant la boule. Origine = a.neck.
  const onNeck = (inner) => ({ a }) => at(a.neck.x, a.neck.y, k(a), inner);
  // Main : tenu au bout du bras droit (bébé : au bord de la boule). Origine = a.hands.r ; bras levé : un peu penché.
  const HAND = 1.6;   // les objets tenus sont dessinés petits : on les grossit pour qu'ils se voient (playtest « Léa »)
  const inHand = (inner) => ({ a }) => at(a.hands.r.x, a.hands.r.y, r1(k(a) * HAND * 100) / 100, inner, a.hands.r.up ? -18 : 8);

  // ════ TÊTE ════
  def("bandeau-eponge", "head", onHead(
    shape("M-40 16 Q0 -2 40 16 L40 25 Q0 7 -40 25 Z", "#ff4f9a", 1.6)
    + line("M-28 14 Q0 2 28 14", "#fff", 2.4, 'opacity=".85"') + line("M-30 22 Q0 10 30 22", "#ffd24d", 2)
  ), { under: true });
  def("casque-grimpe", "head", onHead(
    shape("M-38 26 Q-40 -12 0 -14 Q40 -12 38 26 Q0 16 -38 26 Z", "#ff8a2a", 1.8)
    + line("M-30 8 Q0 -6 30 8", "#ffb36b", 2.4) + dot(0, -3, 2.6, "#fff", 'opacity=".9"')
    + [-20, 0, 20].map((x) => `<rect x="${x - 3}" y="-8" width="6" height="3" rx="1.5" fill="${INK}" opacity=".55"/>`).join("")
    + line("M-36 24 Q-30 40 -18 44", INK, 1.6) + line("M36 24 Q30 40 18 44", INK, 1.6)
  ), { under: true });
  def("chapeau-sorciere", "head", onTop(
    shape("M-34 2 Q0 -10 34 2 Q0 10 -34 2 Z", "#2a1b52", 1.6)
    + shape("M-18 0 L-4 -46 Q2 -52 10 -46 L6 -40 Q10 -44 12 -40 L18 0 Q0 6 -18 0 Z", "#2a1b52", 1.6)
    + shape("M-17 -6 Q0 0 17 -6 L18 0 Q0 6 -18 0 Z", "#8be36b", 1.2)
    + `<rect x="-4" y="-8" width="8" height="7" rx="1" fill="#ffd24d" stroke="${INK}" stroke-width="1.2"/>`
  ));
  // Mythique Disco : Couronne Aurore, prisme qui projette des reflets arc-en-ciel animés.
  def("m-disco", "head", onTop(
    ["#ff4f9a", "#ffb547", "#ffe66b", "#8be36b", "#5ee7ff", "#8f6bff"].map((c, i) =>
      line(`M0 -12 L${-40 + i * 16} -46`, c, 3, `${fx(i)} opacity=".75"`)).join("")
    + shape("M-22 2 L-24 -18 L-12 -8 L0 -26 L12 -8 L24 -18 L22 2 Z", "#f4f0ff", 1.8)
    + shape("M-22 2 L-24 -18 L-12 -8 L0 -26 L12 -8 L24 -18 L22 2 Z", "url(#aurora)", 0, 'opacity=".55"')
    + `<path d="M-6 -6 L0 -16 L6 -6 L0 2 Z" fill="#bff0ff" stroke="${INK}" stroke-width="1.2" class="pt-fx"/>`
    + dot(-14, -4, 2.4, "#ff4f9a") + dot(14, -4, 2.4, "#5ee7ff")
    + `<defs><linearGradient id="aurora" x1="0" x2="1"><stop offset="0" stop-color="#ff4f9a"/><stop offset=".5" stop-color="#ffe66b"/><stop offset="1" stop-color="#5ee7ff"/></linearGradient></defs>`
  ));
  // Mythique Soirées Party : la Boule de Party, mini boule à facettes en chapeau, avec ses rayons.
  def("m-soirees", "head", onTop(
    [0, 1, 2, 3, 4, 5, 6, 7].map((i) => line(`M${Math.cos(i * 0.785) * 22} ${-18 + Math.sin(i * 0.785) * 22} L${Math.cos(i * 0.785) * 34} ${-18 + Math.sin(i * 0.785) * 34}`,
      ["#ff4f9a", "#5ee7ff", "#ffd24d", "#8be36b"][i % 4], 2.4, fx(i))).join("")
    + line("M0 -2 V8", INK, 2) + dot(0, -18, 17, "#c9c2ea", `stroke="${INK}" stroke-width="1.8"`)
    + [[-8, -26], [2, -28], [10, -22], [-12, -16], [-2, -18], [8, -12], [-6, -8], [4, -6], [12, -14]]
      .map(([x, y], i) => `<rect x="${x - 3}" y="${y - 3}" width="6" height="6" fill="${["#fff", "#8f6bff", "#5ee7ff", "#ff4f9a"][i % 4]}" ${fx(i)}/>`).join("")
    + dot(-7, -25, 3.5, "#fff", 'opacity=".9"')
  ));

  // ════ YEUX ════
  def("lunettes-glacier", "eyes", glasses((d) =>
    shape("M-13 -10 H13 Q15 0 13 10 H-13 Q-15 0 -13 -10 Z", "#2a3f6b", 1.6) + line("M-8 -5 L-2 -5", "#bff0ff", 2)
    + `<rect x="${d < 0 ? -17 : 13}" y="-9" width="4" height="18" rx="1.5" fill="#d9d4ea" stroke="${INK}" stroke-width="1.2"/>`, "#d9d4ea"));
  def("loup-bal", "eyes", ({ a }) => {
    const { l, r, rx } = a.eyes, h = rx * 1.15;
    return `<path d="M${r1(l.x - rx * 2)} ${r1(l.y - h * 0.4)} Q${r1(l.x)} ${r1(l.y - h * 1.5)} ${r1((l.x + r.x) / 2)} ${r1(l.y - h * 0.6)} Q${r1(r.x)} ${r1(r.y - h * 1.5)} ${r1(r.x + rx * 2)} ${r1(r.y - h * 0.4)} Q${r1(r.x + rx * 1.4)} ${r1(r.y + h * 1.1)} ${r1(r.x)} ${r1(r.y + h * 0.9)} Q${r1((l.x + r.x) / 2)} ${r1(l.y + h * 0.2)} ${r1(l.x)} ${r1(l.y + h * 0.9)} Q${r1(l.x - rx * 1.4)} ${r1(l.y + h * 1.1)} ${r1(l.x - rx * 2)} ${r1(l.y - h * 0.4)} Z" fill="#6b1d8f" fill-opacity=".92" stroke="${INK}" stroke-width="1.6"/>`
      + `<ellipse cx="${l.x}" cy="${l.y}" rx="${r1(rx * 0.95)}" ry="${r1(rx * 0.75)}" fill="#fff" fill-opacity=".9"/><ellipse cx="${r.x}" cy="${r.y}" rx="${r1(rx * 0.95)}" ry="${r1(rx * 0.75)}" fill="#fff" fill-opacity=".9"/>`
      + `<circle cx="${l.x}" cy="${r1(l.y + rx * 0.1)}" r="${r1(rx * 0.4)}" fill="${INK}"/><circle cx="${r.x}" cy="${r1(r.y + rx * 0.1)}" r="${r1(rx * 0.4)}" fill="${INK}"/>`
      + [0, 1, 2].map((i) => `<circle cx="${r1(l.x - rx * (1.2 - i * 0.6))}" cy="${r1(l.y - h * (1.05 - i * 0.1))}" r="1.3" fill="#ffd24d"/>`).join("");
  });
  def("lunettes-2027", "eyes", ({ a }) => {
    const { l, r, rx } = a.eyes, h = rx * 1.05;
    const digits = (cx, cy, txt) => `<text x="${r1(cx)}" y="${r1(cy + h * 0.38)}" text-anchor="middle" font-size="${r1(h * 1.1)}" font-weight="900" font-family="system-ui,sans-serif" fill="#ffd24d" stroke="${INK}" stroke-width=".9" paint-order="stroke">${txt}</text>`;
    const frame = (p) => `<rect x="${r1(p.x - rx * 1.35)}" y="${r1(p.y - h)}" width="${r1(rx * 2.7)}" height="${r1(h * 2)}" rx="${r1(h * 0.5)}" fill="#ff4f9a" fill-opacity=".35" stroke="#ffd24d" stroke-width="2.4"/>`;
    return frame(l) + frame(r) + digits(l.x, l.y, "20") + digits(r.x, r.y, "27")
      + `<path d="M${r1(l.x + rx * 1.35)} ${r1(l.y - h * 0.3)} H${r1(r.x - rx * 1.35)}" stroke="#ffd24d" stroke-width="2.4"/>`
      + `<path class="pt-fx" d="M${r1(l.x - rx * 1.6)} ${r1(l.y - h * 1.5)} l2 3 l3 -1 l-2 3 l2 3 l-3 -1 l-2 3 l-1 -3 l-3 -1 l3 -1 Z" fill="#fff"/>`;
  });
  def("lunettes-coeur", "eyes", glasses((d) =>
    shape("M0 10 C-18 -2 -14 -16 -5 -13 C-2 -12 0 -9 0 -8 C0 -9 2 -12 5 -13 C14 -16 18 -2 0 10 Z", "#ff4f9a", 1.8, 'fill-opacity=".85"')
    + line("M-8 -8 Q-5 -11 -2 -9", "#fff", 1.8, 'opacity=".9"'), "#ff4f9a"));

  // ════ COU ════
  def("cloche-vache", "neck", onNeck(
    line("M-30 -8 Q0 6 30 -8", "#c0392b", 4.5) + line("M-22 -4 L-18 -2 M-8 0 L-4 1 M8 0 L12 -1 M18 -3 L22 -5", "#fff", 1.5)
    + shape("M-10 2 L10 2 L14 22 Q0 27 -14 22 Z", "#ffcf4d", 1.8) + line("M-8 8 L-4 20", "#fff6c4", 2, 'opacity=".8"')
    + dot(0, 25, 3, "#a8781d", `stroke="${INK}" stroke-width="1.2"`)
  ));
  def("baudrier", "neck", ({ a }) => {
    const { x, y, r } = a.body;
    return `<path d="M${r1(x - r * 0.96)} ${r1(y + r * 0.36)} Q${x} ${r1(y + r * 0.6)} ${r1(x + r * 0.96)} ${r1(y + r * 0.36)}" fill="none" stroke="${INK}" stroke-width="${r1(r * 0.16)}" stroke-linecap="round"/>`
      + `<path d="M${r1(x - r * 0.96)} ${r1(y + r * 0.36)} Q${x} ${r1(y + r * 0.6)} ${r1(x + r * 0.96)} ${r1(y + r * 0.36)}" fill="none" stroke="#3ddc97" stroke-width="${r1(r * 0.11)}" stroke-linecap="round"/>`
      + at(x, y + r * 0.5, k(a), `<rect x="-7" y="-5" width="14" height="10" rx="3" fill="#c9c2ea" stroke="${INK}" stroke-width="1.6"/>`
        + shape("M-4 6 Q-8 16 0 18 Q8 16 4 6", "none", 2) + line("M-14 -2 L-24 6 M14 -2 L24 6", "#3ddc97", 3));
  });
  def("noeud-or", "neck", onNeck(
    shape("M0 2 L-16 -8 Q-19 2 -16 12 Z", "#ffd24d", 1.8) + shape("M0 2 L16 -8 Q19 2 16 12 Z", "#ffd24d", 1.8)
    + line("M-13 -2 L-6 1 M13 -2 L6 1", "#fff6c4", 1.6) + dot(0, 2, 5, "#e8a92a", `stroke="${INK}" stroke-width="1.6"`)
    + dot(-1.5, 0.5, 1.5, "#fff", 'opacity=".9"')
  ));

  // ════ MAIN ════ (origine : le poing ; l'objet monte vers le haut)
  def("micro-chrome", "hand", inHand(
    shape("M-3 2 L3 2 L2 22 L-2 22 Z", "#8f98b8", 1.4) + dot(0, -6, 9, "#dfe4f5", `stroke="${INK}" stroke-width="1.8"`)
    + line("M-6 -9 L6 -3 M-6 -3 L6 -9 M-8 -6 H8", "#9aa3c2", 1.1) + dot(-3, -9, 2.2, "#fff", 'opacity=".9"')
    + `<rect x="-4.5" y="1" width="9" height="4" rx="1.5" fill="#ff4f9a" stroke="${INK}" stroke-width="1.2"/>`
  ));
  def("bouquet-edelweiss", "hand", inHand(
    line("M0 18 L-6 -6 M0 18 L0 -10 M0 18 L7 -5", "#5c9b4b", 2.2)
    + [[-6, -10], [0, -16], [7, -9]].map(([x, y], i) => `<g transform="translate(${x} ${y}) rotate(${i * 20})">`
      + [0, 1, 2, 3, 4, 5].map((j) => `<ellipse rx="2.4" ry="6" transform="rotate(${j * 60}) translate(0 -4)" fill="#f7f7f0" stroke="${INK}" stroke-width=".9"/>`).join("")
      + dot(0, 0, 2.6, "#ffd24d", `stroke="${INK}" stroke-width=".8"`) + "</g>").join("")
  ));
  def("cor-alpes", "hand", ({ a }) => {
    const kk = k(a), { x, y } = a.hands.r;
    return at(x, y, kk, shape("M3 -3 L-60 70 L-54 76 L7 3 Z", "#b07a3c", 1.6)
      + shape("M-60 70 Q-78 84 -66 92 Q-54 92 -54 76 Z", "#c48a46", 1.6)
      + line("M-20 22 L-16 26 M-38 44 L-34 48", "#ffd24d", 2) + dot(3, -3, 3, INK), -35);
  });
  def("mousqueton", "hand", inHand(
    `<path d="M-6 -18 Q-12 -18 -12 -10 L-12 6 Q-12 14 -4 14 L4 14 Q12 14 12 6 L12 -10 Q12 -18 6 -18 Z" fill="none" stroke="${INK}" stroke-width="5"/>`
    + `<path d="M-6 -18 Q-12 -18 -12 -10 L-12 6 Q-12 14 -4 14 L4 14 Q12 14 12 6 L12 -10 Q12 -18 6 -18 Z" fill="none" stroke="#ffb547" stroke-width="3"/>`
    + line("M6 -18 L12 -8", "#c9c2ea", 3)
  ));
  def("piolet-or", "hand", inHand(
    line("M0 22 L0 -24", INK, 6) + line("M0 22 L0 -24", "#ffd24d", 3.6)
    + shape("M-16 -26 Q0 -32 18 -22 L16 -18 Q2 -24 -14 -20 Z", "#ffe27a", 1.6)
    + shape("M18 -22 L26 -14 L16 -18 Z", "#ffd24d", 1.4)
    + `<path class="pt-fx" d="M-20 -34 l1.5 3 l3 1.5 l-3 1.5 l-1.5 3 l-1.5 -3 l-3 -1.5 l3 -1.5 Z" fill="#fff"/>`
    + `<path class="pt-fx" style="animation-delay:.6s" d="M14 -2 l1.2 2.4 l2.4 1.2 l-2.4 1.2 l-1.2 2.4 l-1.2 -2.4 l-2.4 -1.2 l2.4 -1.2 Z" fill="#fff"/>`
  ));
  def("lanterne-citrouille", "hand", inHand(
    line("M0 -2 L0 -8", INK, 2) + line("M-8 -10 Q0 -20 8 -10", INK, 1.6, 'fill="none"')
    + `<ellipse cx="0" cy="8" rx="14" ry="11" fill="#ff8a2a" stroke="${INK}" stroke-width="1.8"/>`
    + line("M-5 -2 Q-6 8 -5 18 M5 -2 Q6 8 5 18", "#e06a10", 1.4)
    + `<path d="M-8 4 l3 -3 l3 3 Z M2 4 l3 -3 l3 3 Z M-7 12 Q0 17 7 12 L4 12 L2 14 L0 12 L-2 14 L-4 12 Z" fill="#ffe66b" ${fx(2)}/>`
    + shape("M-1 -3 Q2 -8 5 -6 Q2 -4 2 -2 Z", "#5c9b4b", 1)
  ));
  def("langue-belle-mere", "hand", inHand(
    `<rect x="-4" y="-2" width="8" height="10" rx="2" fill="#ffd24d" stroke="${INK}" stroke-width="1.4"/>`
    + `<path d="M0 -2 Q-2 -16 10 -18 Q24 -20 26 -8 Q28 2 18 2" fill="none" stroke="${INK}" stroke-width="6.5" stroke-linecap="round"/>`
    + `<path d="M0 -2 Q-2 -16 10 -18 Q24 -20 26 -8 Q28 2 18 2" fill="none" stroke="#5ee7ff" stroke-width="4.5" stroke-linecap="round"/>`
    + `<path d="M0 -2 Q-2 -16 10 -18 Q24 -20 26 -8 Q28 2 18 2" fill="none" stroke="#ff4f9a" stroke-width="4.5" stroke-dasharray="3 4" stroke-linecap="round"/>`
  ));
  def("horloge-minuit", "hand", inHand(
    dot(0, -10, 15, "#fff6e0", `stroke="#ffd24d" stroke-width="3.5"`) + dot(0, -10, 15, "none", `stroke="${INK}" stroke-width="1.2"`)
    + [0, 1, 2, 3].map((i) => `<rect x="-1" y="-23" width="2" height="4" fill="${INK}" transform="rotate(${i * 90} 0 -10)"/>`).join("")
    + line("M0 -10 V-21", INK, 2.2) + line("M0 -10 L1 -18", INK, 2.6) + dot(0, -10, 1.8, "#ff4f9a")
    + dot(-9, -27, 3, "#ffd24d", `stroke="${INK}" stroke-width="1"`) + dot(9, -27, 3, "#ffd24d", `stroke="${INK}" stroke-width="1"`)
    + `<path class="pt-fx" d="M20 -24 l1.2 2.4 l2.4 1.2 l-2.4 1.2 l-1.2 2.4 l-1.2 -2.4 l-2.4 -1.2 l2.4 -1.2 Z" fill="#ffd24d"/>`
  ));
  def("bracelet-entree", "hand", inHand(
    `<ellipse cx="0" cy="2" rx="9" ry="4.5" fill="none" stroke="${INK}" stroke-width="5"/><ellipse cx="0" cy="2" rx="9" ry="4.5" fill="none" stroke="#ff4f9a" stroke-width="3"/>`
    + `<rect x="-6" y="3" width="12" height="7" rx="2" fill="#ffd24d" stroke="${INK}" stroke-width="1.2"/>`
    + `<text x="0" y="8.6" text-anchor="middle" font-size="5" font-weight="900" font-family="system-ui,sans-serif" fill="${INK}">VIP</text>`
  ));
  def("baton-lumineux", "hand", inHand(
    `<rect x="-3.5" y="-30" width="7" height="34" rx="3.5" fill="#5ee7ff" stroke="${INK}" stroke-width="1.6"/>`
    + `<rect x="-7" y="-32" width="14" height="38" rx="7" fill="#5ee7ff" opacity=".28" ${fx(1)}/>`
    + line("M-1 -26 V-6", "#fff", 1.6, 'opacity=".9"') + `<rect x="-3.5" y="2" width="7" height="6" rx="2" fill="#8f6bff" stroke="${INK}" stroke-width="1.2"/>`
  ));
})();
