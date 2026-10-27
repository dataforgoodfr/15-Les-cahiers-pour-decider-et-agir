// Sous-thèmes des propositions (annotation.themes). La proposition se lit
// surlignée dans sa contribution, à côté de la page de l'édition Chabin ; les
// cases cochées s'enregistrent à la validation, qui passe à la suivante à faire.
"use strict";

const $ = (id) => document.getElementById(id);
const etat = { contributions: [], propositions: [], grille: [], miens: {}, rang: 0 };

function lire(cle, defaut) {
  try { return localStorage.getItem(cle) ?? defaut; } catch { return defaut; }
}
function garder(cle, valeur) {
  try { localStorage.setItem(cle, valeur); } catch { /* stockage indisponible */ }
}

// pour filtrer sans se soucier des accents ni des majuscules
const simple = (s) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

function annotateur() { return $("annotateur").value.trim(); }

async function charger() {
  const r = await fetch(`/api/themes?annotateur=${encodeURIComponent(annotateur())}`);
  if (!r.ok) { $("info").textContent = "Le serveur ne sert pas les sous-thèmes."; return; }
  const d = await r.json();
  etat.contributions = d.contributions;
  etat.propositions = d.contributions.flatMap((c) => c.propositions.map((p) => ({ ...p, c })));
  etat.grille = d.grille;
  etat.miens = d.miens;
  construireGrille();
  afficher();
}

function construireGrille() {
  const cases = $("cases");
  cases.replaceChildren();
  for (const groupe of etat.grille) {
    const bloc = document.createElement("div");
    bloc.className = "groupe-theme";
    const titre = document.createElement("h3");
    titre.textContent = groupe.theme;
    bloc.append(titre);
    for (const s of groupe.sous_themes) {
      const label = document.createElement("label");
      label.className = "sous-theme";
      label.dataset.simple = simple(s);
      const boite = document.createElement("input");
      boite.type = "checkbox";
      boite.value = s;
      label.append(boite, ` ${s}`);
      bloc.append(label);
    }
    cases.append(bloc);
  }
}

function afficher() {
  const l = etat.propositions;
  $("avancement").textContent = l.length ? `${Object.keys(etat.miens).length} / ${l.length} faites` : "";
  if (!l.length) {
    $("info").textContent = "Aucune proposition : lancer d'abord « uv run python -m classement.themes.revue ».";
    montrer(false);
    return;
  }
  if (!annotateur()) {
    $("info").textContent = "Indiquez votre prénom pour commencer.";
    montrer(false);
    return;
  }
  montrer(true);
  etat.rang = Math.min(Math.max(etat.rang, 0), l.length - 1);
  const p = l[etat.rang];
  $("position").textContent = `${etat.rang + 1} / ${l.length}`;
  $("contexte").textContent = `${p.c.commune}, contribution ${p.c.contribution}`;
  afficherContribution(p);
  afficherPage(p);
  const mien = etat.miens[p.proposition];
  const coches = new Set(mien?.sous_themes ?? []);
  for (const b of $("cases").querySelectorAll("input")) b.checked = coches.has(b.value);
  $("mal-coupee").checked = mien?.mal_coupee ?? false;
  $("filtre").value = "";
  filtrer();
  $("info").textContent = mien
    ? "Enregistré. Suppr retire l'annotation."
    : "Aucune case cochée : aucun sous-thème n'est traité.";
}

function montrer(oui) {
  for (const id of ["carte", "sous-themes", "valider", "page-chabin"]) $(id).hidden = !oui;
  if (!oui) $("position").textContent = "";
}

function afficherContribution(courante) {
  const bloc = $("contribution");
  bloc.replaceChildren();
  let contexte = "";
  for (const p of courante.c.propositions) {
    if (p.contexte && p.contexte !== contexte) {
      const titre = document.createElement("p");
      titre.className = "intitule";
      titre.textContent = p.contexte;
      bloc.append(titre);
    }
    contexte = p.contexte;
    const ligne = document.createElement("p");
    ligne.className = "ligne-proposition";
    if (p.proposition === courante.proposition) ligne.classList.add("courante");
    if (etat.miens[p.proposition]) ligne.classList.add("faite");
    ligne.textContent = p.texte;
    ligne.title = "Aller à cette proposition";
    ligne.addEventListener("click", () => {
      etat.rang = etat.propositions.findIndex((x) => x.proposition === p.proposition);
      afficher();
    });
    bloc.append(ligne);
  }
  bloc.querySelector(".courante")?.scrollIntoView({ block: "nearest" });
}

function afficherPage(p) {
  const conteneur = $("page-chabin");
  const largeur = Math.round(conteneur.clientWidth * (window.devicePixelRatio || 1)) || 800;
  const img = $("image-page");
  const src = `/api/themes/image?pdf=${encodeURIComponent(p.c.pdf)}&page=${p.page}&largeur=${largeur}`;
  if (img.getAttribute("src") !== src) img.src = src;
  $("legende-page").textContent = `Édition Chabin, page ${p.page}` +
    (p.cadres.length ? "" : " (proposition non retrouvée sur la page : celle de la précédente)");
  const reperes = $("reperes");
  reperes.replaceChildren();
  for (const [x0, y0, x1, y1] of p.cadres) {
    const r = document.createElement("div");
    r.className = "repere-proposition";
    Object.assign(r.style, {
      left: `${(100 * x0) / p.largeur}%`,
      top: `${(100 * y0) / p.hauteur}%`,
      width: `${(100 * (x1 - x0)) / p.largeur}%`,
      height: `${(100 * (y1 - y0)) / p.hauteur}%`,
    });
    reperes.append(r);
  }
  reperes.firstChild?.scrollIntoView({ block: "center", behavior: "smooth" });
}

function filtrer() {
  const motif = simple($("filtre").value.trim());
  for (const label of $("cases").querySelectorAll("label")) {
    label.hidden = motif !== "" && !label.dataset.simple.includes(motif);
  }
  for (const bloc of $("cases").querySelectorAll(".groupe-theme")) {
    bloc.hidden = !bloc.querySelector("label:not([hidden])");
  }
}

async function annoter(sousThemes) {
  const p = etat.propositions[etat.rang];
  if (!p || !annotateur()) return;
  const malCoupee = $("mal-coupee").checked;
  const r = await fetch("/api/themes/annoter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ proposition: p.proposition, annotateur: annotateur(), sous_themes: sousThemes, mal_coupee: malCoupee }),
  });
  if (!r.ok) { $("info").textContent = (await r.json()).erreur; return; }
  if (sousThemes) etat.miens[p.proposition] = { sous_themes: sousThemes, mal_coupee: malCoupee };
  else delete etat.miens[p.proposition];
  if (sousThemes) aFaire(); else afficher();
}

function valider() {
  annoter([...$("cases").querySelectorAll("input:checked")].map((b) => b.value));
}

// la prochaine proposition sans annotation, à partir de la suivante (ou de
// la courante si `depuis` vaut 0)
function aFaire(depuis = 1) {
  const l = etat.propositions;
  if (!l.length || !annotateur()) { afficher(); return; }
  for (let k = depuis; k < l.length + depuis; k++) {
    const i = (etat.rang + k) % l.length;
    if (!(l[i].proposition in etat.miens)) { etat.rang = i; afficher(); return; }
  }
  afficher();
  $("info").textContent = "Toutes les propositions sont faites. Merci !";
}

function aller(pas) { etat.rang += pas; afficher(); }

$("annotateur").value = lire("paires-annotateur", "");
$("annotateur").addEventListener("change", () => {
  garder("paires-annotateur", annotateur());
  etat.rang = 0;
  charger().then(() => aFaire(0));
});
$("prec").addEventListener("click", () => aller(-1));
$("suiv").addEventListener("click", () => aller(1));
$("a-faire").addEventListener("click", () => aFaire());
$("valider").addEventListener("click", valider);
$("filtre").addEventListener("input", filtrer);
$("filtre").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const premier = $("cases").querySelector("label:not([hidden]) input");
    if (premier) premier.checked = !premier.checked;
    $("filtre").value = "";
    filtrer();
    e.preventDefault();
  } else if (e.key === "Escape") {
    $("filtre").value = "";
    filtrer();
    $("filtre").blur();
  }
  e.stopPropagation();
});
document.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLInputElement && e.target.type !== "checkbox") return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "Enter") valider();
  else if (e.key === "/") $("filtre").focus();
  else if (e.key === "c") $("mal-coupee").checked = !$("mal-coupee").checked;
  else if (e.key === "ArrowLeft") aller(-1);
  else if (e.key === "ArrowRight") aller(1);
  else if (e.key === "n") aFaire();
  else if (e.key === "Delete" || e.key === "Backspace") annoter(null);
  else return;
  e.preventDefault();
});
window.addEventListener("resize", () => {
  const p = etat.propositions[etat.rang];
  if (p && annotateur()) afficherPage(p);
});

charger().then(() => { if (etat.propositions.length && annotateur()) aFaire(0); });
