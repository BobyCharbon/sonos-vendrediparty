// Message flottant (#toast) commun à l'app et à /admin. Il entre par le bas et repart par le même chemin ;
// un nouveau message pendant qu'un autre est affiché le remplace sur place (petit rebond) au lieu de rejouer
// toute l'entrée. action : bouton dans le message (ex. « Annuler » après avoir retiré un titre de la file).
let toastTimer;
const TOAST_MS = 3000, TOAST_ACTION_MS = 7000, TOAST_OUT_SAFETY_MS = 400;

function toast(msg, kind = "", action = null) {
  const t = document.getElementById("toast");
  const shown = !t.classList.contains("hidden") && !t.classList.contains("toast-out");
  t.textContent = msg;
  t.className = `toast ${kind}`;
  if (shown) {
    void t.offsetWidth;   // relance le rebond même si le message précédent rebondissait déjà
    t.classList.add("toast-bump");
  }
  if (action) {
    const b = document.createElement("button");
    b.textContent = action.label;
    b.onclick = () => { hideToast(); action.run(); };
    t.append(b);
  }
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, action ? TOAST_ACTION_MS : TOAST_MS);
}

function hideToast() {
  const t = document.getElementById("toast");
  clearTimeout(toastTimer);
  if (t.classList.contains("hidden") || t.classList.contains("toast-out")) return;
  t.classList.add("toast-out");
  const done = () => { if (t.classList.contains("toast-out")) t.className = "toast hidden"; };
  t.addEventListener("animationend", done, { once: true });
  setTimeout(done, TOAST_OUT_SAFETY_MS);   // filet : animations coupées (économie d'énergie, onglet en arrière-plan)
}
