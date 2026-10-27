// Jugement des paires de propositions (annotation.paires). Le jugement
// s'enregistre aussitôt et passe à la paire suivante à faire.
"use strict";

const AIDE = {
  "même proposition": "Elles demandent la même mesure, même en d'autres mots.",
  "même sujet, mesure différente": "Même sujet, mais pas la même demande.",
  "sans rapport": "Elles ne parlent pas de la même chose.",
  "pas une proposition": "L'une des deux est un témoignage, un constat, ou mal coupée.",
};

const $ = (id) => document.getElementById(id);
// la touche physique, pas le caractère : sur un clavier AZERTY, 1 donne « & »
const CHIFFRE = /^(?:Digit|Numpad)(\d)$/;
const etat = { paires: [], miens: {}, litiges: [], possibles: [], mode: "juger", rang: 0 };

function lire(cle, defaut) {
  try { return localStorage.getItem(cle) ?? defaut; } catch { return defaut; }
}
function garder(cle, valeur) {
  try { localStorage.setItem(cle, valeur); } catch { /* stockage indisponible */ }
}

function annotateur() { return $("annotateur").value.trim(); }

function liste() {
  if (etat.mode === "juger") return etat.paires;
  const parId = new Map(etat.paires.map((p) => [p.paire, p]));
  return etat.litiges.map((l) => ({ ...parId.get(l.paire), litige: l }));
}

function jugementCourant(p) {
  return etat.mode === "juger" ? etat.miens[p.paire] : p.litige.adjudication;
}

async function charger() {
  const r = await fetch(`/api/paires?annotateur=${encodeURIComponent(annotateur())}`);
  if (!r.ok) { $("info").textContent = "Le serveur ne sert pas les paires."; return; }
  const d = await r.json();
  Object.assign(etat, { paires: d.paires, miens: d.miens, litiges: d.litiges, possibles: d.jugements_possibles });
  afficher();
}

function afficher() {
  const l = liste();
  const faits = etat.mode === "juger"
    ? Object.keys(etat.miens).length
    : etat.litiges.filter((x) => x.adjudication).length;
  $("compte-litiges").textContent = `(${etat.litiges.length})`;
  $("avancement").textContent = l.length ? `${faits} / ${l.length} faites` : "";
  $("consigne").textContent = etat.mode === "juger"
    ? "Ces deux propositions disent-elles la même chose ? Jugez seul, sans chercher l'avis des autres."
    : "Deux annotateurs ne sont pas d'accord sur cette paire : tranchez.";
  $("mode-juger").setAttribute("aria-pressed", etat.mode === "juger");
  $("mode-adjuger").setAttribute("aria-pressed", etat.mode === "adjuger");
  const jugements = $("jugements");
  jugements.replaceChildren();
  $("avis").hidden = true;
  if (!etat.paires.length) {
    $("info").textContent = "Aucune paire : lancer d'abord « uv run python -m classement.paires ».";
    vider();
    return;
  }
  if (!annotateur()) {
    $("info").textContent = "Indiquez votre prénom pour commencer.";
    vider();
    return;
  }
  if (!l.length) {
    $("info").textContent = "Aucun litige à adjuger pour vous.";
    vider();
    return;
  }
  etat.rang = Math.min(Math.max(etat.rang, 0), l.length - 1);
  const p = l[etat.rang];
  $("propositions").hidden = false;
  $("position").textContent = `${etat.rang + 1} / ${l.length}`;
  for (const cote of ["a", "b"]) {
    $(`contexte-${cote}`).textContent = p[cote].contexte;
    $(`texte-${cote}`).textContent = p[cote].texte;
  }
  if (p.litige) {
    $("avis").hidden = false;
    $("avis").textContent = `Les deux annotateurs ont jugé : « ${p.litige.jugements[0]} » et « ${p.litige.jugements[1]} ».`;
  }
  const courant = jugementCourant(p);
  etat.possibles.forEach((j, i) => {
    const b = document.createElement("button");
    b.className = "jugement";
    b.setAttribute("aria-pressed", j === courant);
    b.title = AIDE[j] ?? "";
    b.innerHTML = `<kbd>${i + 1}</kbd> `;
    b.append(j);
    b.addEventListener("click", () => juger(j));
    jugements.append(b);
  });
  $("info").textContent = courant ? "Enregistré. Suppr retire le jugement." : "";
}

function vider() {
  $("propositions").hidden = true;
  $("position").textContent = "";
  for (const id of ["contexte-a", "texte-a", "contexte-b", "texte-b"]) $(id).textContent = "";
}

async function juger(jugement) {
  const p = liste()[etat.rang];
  if (!p || !annotateur()) return;
  const role = etat.mode === "juger" ? "jugement" : "adjudication";
  const r = await fetch("/api/paires/juger", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paire: p.paire, annotateur: annotateur(), jugement, role }),
  });
  if (!r.ok) { $("info").textContent = (await r.json()).erreur; return; }
  if (role === "jugement") {
    if (jugement) etat.miens[p.paire] = jugement; else delete etat.miens[p.paire];
  } else {
    p.litige.adjudication = jugement;
  }
  if (jugement) aFaire(); else afficher();
}

// la prochaine paire sans jugement, à partir de la suivante (ou de la
// courante si `depuis` vaut 0)
function aFaire(depuis = 1) {
  const l = liste();
  if (!l.length || !annotateur()) { afficher(); return; }
  for (let k = depuis; k < l.length + depuis; k++) {
    const i = (etat.rang + k) % l.length;
    if (!jugementCourant(l[i])) { etat.rang = i; afficher(); return; }
  }
  afficher();
  $("info").textContent = "Toutes les paires sont faites. Merci !";
}

function aller(pas) { etat.rang += pas; afficher(); }

function changerMode(mode) {
  etat.mode = mode;
  etat.rang = 0;
  aFaire(0);
}

$("annotateur").value = lire("paires-annotateur", "");
$("annotateur").addEventListener("change", () => {
  garder("paires-annotateur", annotateur());
  etat.rang = 0;
  charger().then(() => aFaire(0));
});
$("mode-juger").addEventListener("click", () => changerMode("juger"));
$("mode-adjuger").addEventListener("click", () => changerMode("adjuger"));
$("prec").addEventListener("click", () => aller(-1));
$("suiv").addEventListener("click", () => aller(1));
$("a-faire").addEventListener("click", () => aFaire());
document.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement || e.ctrlKey || e.metaKey || e.altKey) return;
  const n = Number(CHIFFRE.exec(e.code)?.[1] ?? NaN);
  if (n >= 1 && n <= etat.possibles.length) juger(etat.possibles[n - 1]);
  else if (e.key === "ArrowLeft") aller(-1);
  else if (e.key === "ArrowRight") aller(1);
  else if (e.key === "n") aFaire();
  else if (e.key === "Delete" || e.key === "Backspace") juger(null);
  else return;
  e.preventDefault();
});

charger().then(() => { if (etat.paires.length && annotateur()) aFaire(0); });
