// Annotation des cahiers : feuilleter, noter, revoir des listes.
// Les positions sont en points PDF, dans le repère de la page affichée.
"use strict";

const $ = (id) => document.getElementById(id);
const SVG = "http://www.w3.org/2000/svg";
const TYPES = { "dactylographiée": "D", "manuscrite": "M", "mixte": "MD", "vierge": "V" };

const etat = {
  etiquettes: [],     // à plat, dans l'ordre des raccourcis 1 à 9…
  groupes: {},        // groupe -> étiquettes, pour les menus
  problemes: [],      // problèmes qu'on peut cocher sur une page
  types: [],          // types de page, pour corriger le typage
  rotations: new Map(), // "fichier|page" -> 90 | 180 | 270 (affichage seulement)
  lignes: new Map(),  // "fichier|page" -> lignes OCR positionnées (affichage local)
  vignettes: new Map(), // page -> <img> de la vignette, sans src avant chargement
  liste: null,        // {nom, titre, consigne, elements}
  index: -1,          // élément courant de la liste
  cahier: null,       // {fichier, pages, notes}
  page: 1,
  zoom: null,         // largeur affichée en pixels ; null : ajustée à la vue
  statuts: new Map(), // "fichier|page" -> "vue" | "a_revoir"
  retablis: new Set(), // "fichier|page|id" des repérages rétablis (listes à masquer)
  note: null,         // identifiant de la note ouverte dans le formulaire
  brouillon: null,    // position d'une note en cours de création
  feuilles: [],       // par page : {feuille, image, calque}
};

// ---------- utilitaires ----------

async function api(url, corps) {
  const options = corps === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  };
  const reponse = await fetch(url, options);
  const donnees = await reponse.json();
  if (!reponse.ok) throw new Error(donnees.erreur || reponse.statusText);
  return donnees;
}

let minuterieMessage;
function message(texte) {
  const m = $("message");
  m.textContent = texte;
  m.classList.add("visible");
  clearTimeout(minuterieMessage);
  minuterieMessage = setTimeout(() => m.classList.remove("visible"), 1800);
}

function element(nom, attributs = {}, texte) {
  const e = nom === "svg" || ["rect", "circle", "line", "text", "g", "title"].includes(nom)
    ? document.createElementNS(SVG, nom) : document.createElement(nom);
  for (const [k, v] of Object.entries(attributs)) e.setAttribute(k, v);
  if (texte !== undefined) e.textContent = texte;
  return e;
}

const cle = (fichier, page) => `${fichier}|${page}`;
const tache = () => encodeURIComponent(etat.liste?.tache || "");
const aMasquer = () => etat.liste?.mode === "masquer";
const PERSONNELLES = "Données personnelles";
// étiquettes des touches 1 à 9 : les données personnelles dans une liste à
// masquer, toutes les étiquettes sinon
const raccourcis = () => (aMasquer() ? etat.groupes[PERSONNELLES] : etat.etiquettes).slice(0, 9);
const pageCourante = () => etat.cahier.pages[etat.page - 1];
const nomCourt = (fichier) => fichier.replace(/\.pdf$/i, "");

function remplirEtiquettes(select, choisie) {
  select.replaceChildren(...Object.entries(etat.groupes).map(([groupe, noms]) => {
    const g = element("optgroup", { label: groupe });
    g.append(...noms.map((nom) => {
      const rang = raccourcis().indexOf(nom) + 1;
      return element("option", { value: nom }, rang ? `${rang}. ${nom}` : nom);
    }));
    return g;
  }));
  if (choisie) select.value = choisie;
}

function remplirSelect(select, valeurs, choisie) {
  select.replaceChildren(...valeurs.map((v) => element("option", { value: v }, v)));
  if (choisie) select.value = choisie;
}

// ---------- adresse (pour retrouver sa place au rechargement) ----------

function ecrireAdresse() {
  const p = new URLSearchParams();
  if (etat.cahier) { p.set("f", etat.cahier.fichier); p.set("p", etat.page); }
  if (etat.liste) { p.set("l", etat.liste.nom); p.set("i", etat.index); }
  history.replaceState(null, "", "#" + p.toString());
}

async function lireAdresse() {
  const p = new URLSearchParams(location.hash.slice(1));
  if (p.get("l")) {
    $("choix-liste").value = p.get("l");
    await choisirListe(p.get("l"), Number(p.get("i") ?? 0));
  } else if (p.get("f")) {
    await ouvrirCahier(p.get("f"), Number(p.get("p") ?? 1));
  }
}

// ---------- cahier et pages ----------

async function ouvrirCahier(fichier, page = 1, defilerVers) {
  try {
    etat.cahier = await api(`/api/cahier?fichier=${encodeURIComponent(fichier)}&tache=${tache()}`);
  } catch (e) {
    message(`Cahier introuvable : ${fichier}`);
    return;
  }
  for (const [p, s] of Object.entries(etat.cahier.statuts)) etat.statuts.set(cle(fichier, p), s);
  for (const [p, id] of etat.cahier.retablis) etat.retablis.add(`${cle(fichier, p)}|${id}`);
  $("titre-cahier").textContent = nomCourt(fichier);
  $("titre-cahier").classList.remove("discret");
  $("total-pages").textContent = `/ ${etat.cahier.pages.length}`;
  $("champ-page").max = etat.cahier.pages.length;
  dessinerVignettes();
  construireFeuilles();
  allerPage(page, defilerVers);
}

// L'affichage peut pivoter d'un quart de tour, page par page. Les notes, elles,
// restent dans le repère du PDF : on convertit à l'affichage et au clic.
const TRANSFORMATIONS = {
  0: "none",
  90: "rotate(90deg) translateY(-100%)",
  180: "rotate(180deg) translate(-100%, -100%)",
  270: "rotate(270deg) translateX(-100%)",
};

function rotation() {
  return etat.rotations.get(cle(etat.cahier.fichier, etat.page)) || 0;
}

function dimensionsVue() {
  const p = pageCourante();
  return rotation() % 180 ? [p.hauteur, p.largeur] : [p.largeur, p.hauteur];
}

function versVue(x, y) {
  const p = pageCourante();
  switch (rotation()) {
    case 90: return [p.hauteur - y, x];
    case 180: return [p.largeur - x, p.hauteur - y];
    case 270: return [y, p.largeur - x];
    default: return [x, y];
  }
}

function versPage(u, v) {
  const p = pageCourante();
  switch (rotation()) {
    case 90: return [v, p.hauteur - u];
    case 180: return [p.largeur - u, p.hauteur - v];
    case 270: return [p.largeur - v, u];
    default: return [u, v];
  }
}

function pivoter() {
  if (!etat.cahier) return;
  const c = cle(etat.cahier.fichier, etat.page);
  const r = (rotation() + 90) % 360;
  if (r) etat.rotations.set(c, r); else etat.rotations.delete(c);
  try { localStorage.setItem("rotations", JSON.stringify([...etat.rotations])); } catch { /* sans stockage */ }
  dimensionner();
  allerPage(etat.page);
}

function largeurAffichee() {
  if (etat.zoom) return etat.zoom;
  return Math.max(300, $("vue").clientWidth - 32);
}

// Les pages du cahier défilent les unes sous les autres, chacune avec son
// image et son calque. La page courante est celle qui occupe le haut de la
// vue : le panneau, les vignettes et les fonctions du calque travaillent sur
// elle ; `surPage` les fait travailler sur une autre.

const calqueCourant = () => etat.feuilles[etat.page - 1].calque;

function surPage(n, fn) {
  const courante = etat.page;
  etat.page = n;
  try { return fn(); } finally { etat.page = courante; }
}

let observateur;
function construireFeuilles() {
  observateur?.disconnect();
  // une image se charge quand sa page approche de la vue
  observateur = new IntersectionObserver((entrees) => {
    for (const e of entrees) if (e.isIntersecting) chargerImage(Number(e.target.dataset.page));
  }, { root: $("vue"), rootMargin: "100% 0px" });
  etat.feuilles = etat.cahier.pages.map((p) => {
    const feuille = element("div", { class: "feuille" });
    feuille.dataset.page = p.page;
    const image = element("img", { class: "image", alt: "", draggable: "false" });
    const calque = element("svg", { class: "calque", preserveAspectRatio: "none" });
    feuille.append(image, calque);
    observateur.observe(feuille);
    return { feuille, image, calque };
  });
  $("feuilles").replaceChildren(...etat.feuilles.map((f) => f.feuille));
  $("vide").hidden = true;
  dimensionner();
}

function dimensionner() {
  // taille de chaque feuille selon le zoom et sa rotation
  for (const p of etat.cahier.pages) {
    surPage(p.page, () => {
      const { feuille, image, calque } = etat.feuilles[p.page - 1];
      const [largeurVue, hauteurVue] = dimensionsVue();
      const s = largeurAffichee() / largeurVue; // pixels par point
      feuille.style.width = `${largeurVue * s}px`;
      feuille.style.height = `${hauteurVue * s}px`;
      image.style.width = `${p.largeur * s}px`;
      image.style.height = `${p.hauteur * s}px`;
      image.style.transform = TRANSFORMATIONS[rotation()];
      calque.setAttribute("viewBox", `0 0 ${largeurVue} ${hauteurVue}`);
      if (image.getAttribute("src")) chargerImage(p.page); // à la nouvelle largeur
      dessinerCalque();
    });
  }
}

function chargerImage(n) {
  surPage(n, () => {
    const p = pageCourante();
    const url = urlImage(etat.cahier.fichier, n, p.largeur * (largeurAffichee() / dimensionsVue()[0]));
    const { image } = etat.feuilles[n - 1];
    if (image.getAttribute("src") !== url) image.src = url;
  });
}

let defilementProgramme = false; // le défilement vient de allerPage, pas de l'utilisateur

function allerPage(n, defilerVers) {
  // défile jusqu'à la page n, à son haut ou à l'ordonnée `defilerVers` (points PDF)
  if (!etat.cahier) return;
  activerPage(Math.min(Math.max(1, n), etat.cahier.pages.length));
  const { feuille } = etat.feuilles[etat.page - 1];
  let haut = 0, gauche = 0;
  if (defilerVers !== undefined) {
    const s = largeurAffichee() / dimensionsVue()[0];
    const [u, v] = versVue(0, defilerVers);
    haut = Math.max(0, v * s - 120);
    gauche = rotation() % 180 ? Math.max(0, u * s - 120) : 0;
  }
  defilementProgramme = true;
  $("vue").scrollTop = feuille.offsetTop + haut;
  $("vue").scrollLeft = gauche ? feuille.offsetLeft + gauche : 0;
}

function activerPage(n) {
  // la page n devient la page courante, sans défiler
  if (!etat.cahier) return;
  fermerFormulaire();
  const ancienne = etat.page;
  etat.page = n;
  // l'ancienne page perd sa note choisie et son brouillon
  if (ancienne !== n && etat.feuilles[ancienne - 1]) surPage(ancienne, dessinerCalque);
  $("champ-page").value = n;
  $("pivoter").classList.toggle("actif", rotation() !== 0);
  dessinerCalque();
  dessinerNotes();
  dessinerStatut();
  dessinerInfos();
  marquerVignette();
  ecrireAdresse();
  planifier();
}

function pageEnVue() {
  // la page sous le premier tiers de la vue
  const repere = $("vue").scrollTop + $("vue").clientHeight / 3;
  let n = 1;
  for (const { feuille } of etat.feuilles) {
    if (feuille.offsetTop > repere) break;
    n = Number(feuille.dataset.page);
  }
  return n;
}

let imageDefilement = 0;
$("vue").addEventListener("scroll", () => {
  if (defilementProgramme) { defilementProgramme = false; return; }
  if (!etat.cahier || trace || glisse) return;
  cancelAnimationFrame(imageDefilement);
  imageDefilement = requestAnimationFrame(() => {
    const n = pageEnVue();
    if (n !== etat.page) activerPage(n);
  });
});

function dessinerCalques() {
  for (const p of etat.cahier.pages) surPage(p.page, dessinerCalque);
}

// ---------- calque : repérages et notes ----------

function echelle() {
  // points par pixel affiché : pour garder textes et pastilles à taille fixe
  return dimensionsVue()[0] / largeurAffichee();
}

function marquesDeLaPage() {
  if (!etat.liste || !$("voir-marques").checked) return [];
  return etat.liste.elements
    .filter((e) => e.fichier === etat.cahier.fichier && e.page === etat.page)
    .flatMap((e) => e.marques || []);
}

function notesDeLaPage() {
  return etat.cahier.notes
    .filter((n) => n.page === etat.page)
    .sort((a, b) => a.cree.localeCompare(b.cree));
}

function cadreVue(x0, y0, x1, y1) {
  // cadre (en points PDF) converti en cadre affiché, coins remis dans l'ordre
  const [a, b] = versVue(x0, y0);
  const [c, d] = versVue(x1, y1);
  return [Math.min(a, c), Math.min(b, d), Math.max(a, c), Math.max(b, d)];
}

function forme(x0, y0, x1, y1, classe) {
  const [u0, v0, u1, v1] = cadreVue(x0, y0, x1, y1);
  if (u1 - u0 < 0.5 && v1 - v0 < 0.5) {
    return element("circle", { cx: u0, cy: v0, r: 7 * echelle(), class: classe });
  }
  return element("rect", { x: u0, y: v0, width: u1 - u0, height: v1 - v0, class: classe });
}

function dessinerCalque() {
  const calque = calqueCourant();
  calque.replaceChildren();
  const p = pageCourante();
  const taille = 12 * echelle();
  // le plus grand d'abord : un petit repérage reste au-dessus, donc cliquable
  const aire = (m) => Math.abs(((m.x1 ?? p.largeur) - (m.x0 ?? 0)) * ((m.y1 ?? m.y0) - m.y0));
  for (const m of marquesDeLaPage().sort((a, b) => aire(b) - aire(a))) {
    const [u0, v0, u1, v1] = cadreVue(m.x0 ?? 0, m.y0, m.x1 ?? p.largeur, m.y1 ?? m.y0);
    if (aMasquer()) { calque.append(...masque(m, u0, v0, u1, v1, taille)); continue; }
    const trait = Math.min(u1 - u0, v1 - v0) < 0.5;
    calque.append(trait
      ? element("line", { x1: u0, y1: v0, x2: u1, y2: v1, class: "marque" })
      : element("rect", { x: u0, y: v0, width: u1 - u0, height: v1 - v0, class: "marque" }));
    if (m.etiquette) {
      calque.append(element("text", {
        x: u0 + 4 * echelle(), y: v0 - 4 * echelle(), class: "etiquette-marque", "font-size": taille,
      }, m.etiquette));
    }
  }
  for (const l of lignesOcr()) {
    const [u0, v0, u1, v1] = cadreVue(l.x0, l.y0, l.x1, l.y1);
    const r = element("rect", { x: u0, y: v0, width: u1 - u0, height: v1 - v0, class: "ligne-ocr" });
    r.append(element("title", {}, l.texte));
    calque.append(r);
  }
  notesDeLaPage().forEach((n, i) => {
    const f = forme(n.x0, n.y0, n.x1, n.y1, "note" + (n.id === etat.note ? " courant" : ""));
    f.dataset.id = n.id;
    // une note ouverte se déplace en la glissant ; sinon, un clic l'ouvre
    f.addEventListener("pointerdown", (ev) => {
      ev.stopPropagation();
      if (n.id === etat.note) commencerGlisse(ev, n, "deplacer"); else ouvrirNote(n.id);
    });
    const [, v0, u1] = cadreVue(n.x0, n.y0, n.x1, n.y1);
    calque.append(f, element("text", {
      x: u1 + 6 * echelle(), y: v0 + taille / 2, class: "numero-note", "font-size": taille,
    }, String(i + 1)));
    if (n.id === etat.note && (n.x0 !== n.x1 || n.y0 !== n.y1)) calque.append(...poignees(n));
  });
  if (etat.brouillon) {
    const b = etat.brouillon;
    calque.append(forme(b.x0, b.y0, b.x1, b.y1, "trace"));
  }
}

function estRetabli(m) {
  return etat.retablis.has(`${cle(etat.cahier.fichier, etat.page)}|${m.id}`);
}

function masque(m, u0, v0, u1, v1, taille) {
  // liste à masquer : le repérage est caché par défaut ; un clic le rétablit
  const retabli = estRetabli(m);
  const r = element("rect", {
    x: u0, y: v0, width: u1 - u0, height: v1 - v0, class: "masque" + (retabli ? " retabli" : ""),
  });
  r.append(element("title", {}, `${m.etiquette} : ${retabli ? "rétabli (clic pour recacher)" : "caché (clic pour rétablir)"}`));
  r.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); basculerMasque(m); });
  const formes = [r];
  if (retabli) {
    formes.push(element("text", {
      x: u0 + 2 * echelle(), y: v0 - 3 * echelle(), class: "etiquette-retabli", "font-size": taille * 0.8,
    }, "rétabli"));
  }
  return formes;
}

async function basculerMasque(m) {
  const retabli = !estRetabli(m);
  await api("/api/retablir", {
    fichier: etat.cahier.fichier, page: etat.page, marque: m, retabli,
  });
  const c = `${cle(etat.cahier.fichier, etat.page)}|${m.id}`;
  if (retabli) etat.retablis.add(c); else etat.retablis.delete(c);
  message(retabli ? `${m.etiquette} rétabli` : `${m.etiquette} caché`);
  dessinerCalque();
}

function poignees(n) {
  // une poignée à chaque coin, dans le repère du PDF : juste quelle que soit
  // la rotation de l'affichage
  const cote = 10 * echelle();
  return [["x0", "y0"], ["x1", "y0"], ["x0", "y1"], ["x1", "y1"]].map((prise) => {
    const [u, v] = versVue(n[prise[0]], n[prise[1]]);
    const h = element("rect", { x: u - cote / 2, y: v - cote / 2, width: cote, height: cote, class: "poignee" });
    h.addEventListener("pointerdown", (ev) => { ev.stopPropagation(); commencerGlisse(ev, n, prise); });
    return h;
  });
}

let glisse = null; // note qu'on déplace ou redimensionne
function commencerGlisse(ev, n, prise) {
  ev.preventDefault();
  calqueCourant().setPointerCapture(ev.pointerId);
  glisse = { n, prise, depart: pointPdf(ev), origine: { x0: n.x0, y0: n.y0, x1: n.x1, y1: n.y1 } };
}

function suivreGlisse(ev) {
  const { n, prise, depart, origine } = glisse;
  const d = pointPdf(ev);
  if (prise === "deplacer") {
    const dx = d.x - depart.x, dy = d.y - depart.y;
    Object.assign(n, { x0: origine.x0 + dx, x1: origine.x1 + dx, y0: origine.y0 + dy, y1: origine.y1 + dy });
  } else {
    n[prise[0]] = d.x;
    n[prise[1]] = d.y;
  }
  dessinerCalque();
}

async function finirGlisse() {
  const { n, origine } = glisse;
  glisse = null;
  const cadre = {
    x0: Math.min(n.x0, n.x1), y0: Math.min(n.y0, n.y1), x1: Math.max(n.x0, n.x1), y1: Math.max(n.y0, n.y1),
  };
  if (["x0", "y0", "x1", "y1"].every((k) => Math.abs(n[k] - origine[k]) < 0.5)) {
    Object.assign(n, origine);
    return;
  }
  try {
    await api("/api/notes/modifier", { id: n.id, ...cadre });
    Object.assign(n, cadre);
    message("Note déplacée");
  } catch (e) {
    Object.assign(n, origine);
    message(`Échec : ${e.message}`);
  }
  dessinerCalque();
}

function lignesOcr() {
  if (!$("voir-ocr").checked) return [];
  const c = cle(etat.cahier.fichier, etat.page);
  if (etat.lignes.has(c)) return etat.lignes.get(c);
  etat.lignes.set(c, []);
  api(`/api/lignes?fichier=${encodeURIComponent(etat.cahier.fichier)}&page=${etat.page}`)
    .then((lignes) => {
      etat.lignes.set(c, lignes);
      if (cle(etat.cahier.fichier, etat.page) === c) dessinerCalque();
    })
    .catch(() => etat.lignes.delete(c));
  return [];
}

function pointPdf(ev) {
  // point cliqué, en points PDF (repère de la page, pas de l'affichage)
  const calque = calqueCourant();
  const pt = calque.createSVGPoint();
  pt.x = ev.clientX;
  pt.y = ev.clientY;
  const r = pt.matrixTransform(calque.getScreenCTM().inverse());
  const [largeurVue, hauteurVue] = dimensionsVue();
  const [x, y] = versPage(
    Math.min(Math.max(0, r.x), largeurVue), Math.min(Math.max(0, r.y), hauteurVue),
  );
  return { x, y };
}

let trace = null;
// en capture : la page cliquée devient courante avant que ses notes ne
// reçoivent le clic
$("feuilles").addEventListener("pointerdown", (ev) => {
  const feuille = ev.target.closest(".feuille");
  if (feuille && Number(feuille.dataset.page) !== etat.page) activerPage(Number(feuille.dataset.page));
}, true);
$("feuilles").addEventListener("pointerdown", (ev) => {
  if (!etat.cahier || ev.button !== 0 || !ev.target.closest(".calque")) return;
  ev.preventDefault();
  calqueCourant().setPointerCapture(ev.pointerId);
  const d = pointPdf(ev);
  trace = { depart: ev, x0: d.x, y0: d.y };
  etat.note = null;
  etat.brouillon = { x0: d.x, y0: d.y, x1: d.x, y1: d.y };
  dessinerCalque();
});
$("feuilles").addEventListener("pointermove", (ev) => {
  if (glisse) { suivreGlisse(ev); return; }
  if (!trace) return;
  const d = pointPdf(ev);
  etat.brouillon = { x0: trace.x0, y0: trace.y0, x1: d.x, y1: d.y };
  dessinerCalque();
});
$("feuilles").addEventListener("pointerup", (ev) => {
  if (glisse) { finirGlisse(); return; }
  if (!trace) return;
  const bouge = Math.hypot(ev.clientX - trace.depart.clientX, ev.clientY - trace.depart.clientY) > 4;
  const d = pointPdf(ev);
  const x0 = Math.min(trace.x0, d.x), x1 = Math.max(trace.x0, d.x);
  const y0 = Math.min(trace.y0, d.y), y1 = Math.max(trace.y0, d.y);
  etat.brouillon = bouge ? { x0, y0, x1, y1 } : { x0: trace.x0, y0: trace.y0, x1: trace.x0, y1: trace.y0 };
  trace = null;
  if (aMasquer()) {
    // le rectangle devient une note de l'étiquette courante ; un simple clic
    // ne fait que désélectionner
    if (bouge) poserNoteRapide(etat.brouillon, $("etiquette").value);
    else { fermerFormulaire(); rafraichirPage(); }
    return;
  }
  // saisie rapide : un glisser caviarde, un clic pose un début de
  // contribution, un double clic une fin
  if (bouge) poserNoteRapide(etat.brouillon, etiquetteMasque());
  else cliquer(etat.brouillon);
});

const DEBUT = "début de contribution";
const FIN = "fin de contribution";
const DOUBLE_CLIC = 300; // ms
let clic = null; // clic simple en attente : un second clic en fait une fin

function cliquer(point) {
  // la page est retenue au clic : on a pu défiler avant la fin du délai
  const page = etat.page;
  if (clic && clic.page === page && Math.hypot(point.x0 - clic.point.x0, point.y0 - clic.point.y0) < 10) {
    clearTimeout(clic.minuterie);
    clic = null;
    poserNoteRapide(point, FIN, page);
    return;
  }
  if (clic) { clearTimeout(clic.minuterie); poserNoteRapide(clic.point, DEBUT, clic.page); }
  clic = { point, page, minuterie: setTimeout(() => { clic = null; poserNoteRapide(point, DEBUT, page); }, DOUBLE_CLIC) };
}

function etiquetteMasque() {
  // l'étiquette courante si c'est une donnée personnelle, sinon la dernière
  // du groupe (bloc de coordonnées)
  const courante = $("etiquette").value;
  return etat.groupes[PERSONNELLES].includes(courante) ? courante : etat.groupes[PERSONNELLES].at(-1);
}

async function poserNoteRapide(cadre, etiquette, page = etat.page) {
  try {
    const note = await api("/api/notes", {
      fichier: etat.cahier.fichier, page, ...cadre, etiquette, texte: "",
    });
    etat.cahier.notes.push(note);
    // la note posée reste choisie : Suppr l'annule
    if (page === etat.page) etat.note = note.id;
    message(`${etiquette} (Suppr pour annuler)`);
  } catch (e) {
    message(`Échec : ${e.message}`);
  }
  if (page === etat.page) etat.brouillon = null;
  else surPage(page, dessinerCalque);
  rafraichirPage();
}

// ---------- formulaire et liste des notes ----------

function ouvrirFormulaire(note) {
  const f = $("formulaire-note");
  f.hidden = false;
  remplirEtiquettes($("note-etiquette"), note ? note.etiquette : $("etiquette").value);
  $("note-texte").value = note ? note.texte || "" : "";
  $("note-supprimer").hidden = !note;
  // en masquage, le clavier reste aux raccourcis (étiquette, Suppr)
  if (!aMasquer()) $("note-texte").focus();
}

function fermerFormulaire() {
  $("formulaire-note").hidden = true;
  etat.note = null;
  etat.brouillon = null;
}

function ouvrirNote(id) {
  etat.note = id;
  etat.brouillon = null;
  const note = etat.cahier.notes.find((n) => n.id === id);
  dessinerCalque();
  dessinerNotes();
  ouvrirFormulaire(note);
}

$("formulaire-note").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const champs = { etiquette: $("note-etiquette").value, texte: $("note-texte").value };
  try {
    if (etat.note) {
      await api("/api/notes/modifier", { id: etat.note, ...champs });
      Object.assign(etat.cahier.notes.find((n) => n.id === etat.note), champs);
      message("Note modifiée");
    } else if (etat.brouillon) {
      const note = await api("/api/notes", {
        fichier: etat.cahier.fichier, page: etat.page, ...etat.brouillon, ...champs,
      });
      etat.cahier.notes.push(note);
      message("Note enregistrée");
    }
  } catch (e) {
    message(`Échec : ${e.message}`);
    return;
  }
  fermerFormulaire();
  rafraichirPage();
});

$("note-annuler").addEventListener("click", () => { fermerFormulaire(); rafraichirPage(); });

$("note-supprimer").addEventListener("click", () => supprimerNote());

async function supprimerNote() {
  if (!etat.note) return;
  await api("/api/notes/supprimer", { id: etat.note });
  etat.cahier.notes = etat.cahier.notes.filter((n) => n.id !== etat.note);
  message("Note supprimée");
  fermerFormulaire();
  rafraichirPage();
}

$("note-texte").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) $("formulaire-note").requestSubmit();
});

function dessinerNotes() {
  const liste = $("notes");
  liste.replaceChildren();
  notesDeLaPage().forEach((n, i) => {
    const li = element("li", { class: n.id === etat.note ? "courant" : "" });
    li.append(
      element("span", { class: "numero" }, String(i + 1)),
      element("span", {}, n.etiquette),
    );
    if (n.texte) li.append(element("span", { class: "texte" }, n.texte));
    li.addEventListener("click", () => ouvrirNote(n.id));
    liste.append(li);
  });
  if (!liste.children.length) liste.append(element("li", { class: "discret" }, "Aucune note sur cette page."));
}

async function accepterMarques() {
  // les repérages qui proposent une note (champ « note ») deviennent des notes,
  // sauf ceux qu'une note de même étiquette recouvre déjà
  if (!etat.cahier) return;
  if (aMasquer()) { message("Liste à masquer : tout est déjà caché, cliquer pour rétablir"); return; }
  const deja = notesDeLaPage();
  const recouvre = (m, n) => n.etiquette === m.note
    && Math.min(m.x1, Math.max(n.x0, n.x1)) > Math.max(m.x0, Math.min(n.x0, n.x1))
    && Math.min(m.y1, Math.max(n.y0, n.y1)) > Math.max(m.y0, Math.min(n.y0, n.y1));
  const nouvelles = marquesDeLaPage().filter((m) => m.note && !deja.some((n) => recouvre(m, n)));
  for (const m of nouvelles) {
    const note = await api("/api/notes", {
      fichier: etat.cahier.fichier, page: etat.page,
      x0: m.x0, y0: m.y0, x1: m.x1, y1: m.y1, etiquette: m.note, texte: "",
    });
    etat.cahier.notes.push(note);
  }
  message(nouvelles.length ? `${nouvelles.length} repérage(s) accepté(s)` : "Rien à accepter");
  rafraichirPage();
}

function rafraichirPage() {
  dessinerCalque();
  dessinerNotes();
  marquerVignette();
}

// ---------- statut des pages ----------

async function poserStatut(statut, basculer = true) {
  if (!etat.cahier) return;
  const c = cle(etat.cahier.fichier, etat.page);
  const nouveau = basculer && etat.statuts.get(c) === statut ? null : statut;
  await api("/api/statut", {
    fichier: etat.cahier.fichier, page: etat.page, statut: nouveau, tache: etat.liste?.tache || null,
  });
  if (nouveau) etat.statuts.set(c, nouveau); else etat.statuts.delete(c);
  dessinerStatut();
  dessinerInfos();
  marquerVignette();
  dessinerElements();
}

function dessinerStatut() {
  const s = etat.statuts.get(cle(etat.cahier.fichier, etat.page));
  for (const b of document.querySelectorAll("button.statut")) {
    b.classList.toggle("actif", b.dataset.statut === s);
  }
}

$("statut-vue").addEventListener("click", () => poserStatut("vue"));
$("statut-revoir").addEventListener("click", () => poserStatut("a_revoir"));

// ---------- informations sur la page ----------

function chiffre(x, decimales) {
  return Number(x).toLocaleString("fr-FR", { maximumFractionDigits: decimales });
}

function listeConstats(ul, constats) {
  ul.replaceChildren(...(constats.length
    ? constats.map((c) => element("li", {}, c))
    : [element("li", { class: "rien" }, "Rien de signalé.")]));
}

function dessinerInfos() {
  const p = pageCourante();
  $("infos").hidden = false;
  $("infos-numero").textContent = `${etat.page} / ${etat.cahier.pages.length}`;
  const proprietes = [
    ["typage", p.type || "—"],
    ["service", p.service ? "oui" : "non"],
  ];
  if (p.type) {
    proprietes.push(["encre", chiffre(p.encre, 4)], ["qualité", chiffre(p.qualite, 3)],
      ["mots", chiffre(p.mots, 0)]);
  }
  if (p.rotation_pdf) proprietes.push(["rotation du PDF", `${p.rotation_pdf}°`]);
  $("typage").replaceChildren(...proprietes.flatMap(([k, v]) => [element("dt", {}, k), element("dd", {}, v)]));
  $("type-verifie").value = p.type_verifie || p.type || "";
  // une page vue sans correction confirme son typage
  const vue = etat.statuts.get(cle(etat.cahier.fichier, etat.page)) === "vue";
  $("source-type").textContent = p.type_verifie ? "corrigé"
    : vue && p.type ? "confirmé (page vue)" : p.type ? "typage automatique" : "inconnu";
  $("source-type").classList.toggle("verifie", Boolean(p.type_verifie) || (vue && Boolean(p.type)));
  $("problemes").replaceChildren(...etat.problemes.map((nom) => {
    const caseACocher = element("input", { type: "checkbox" });
    caseACocher.checked = probleme(p, nom);
    caseACocher.addEventListener("change", () => qualifier(nom, caseACocher.checked));
    const label = element("label", {
      title: p.problemes_auto.includes(nom) ? "Coché d'avance par une analyse : décocher s'il est faux" : "",
    });
    label.append(caseACocher, nom);
    if (p.problemes_auto.includes(nom) && !(nom in p.problemes)) {
      label.append(element("span", { class: "detecte" }, "détecté"));
    }
    return label;
  }));
  $("remarque-page").value = p.remarque || "";
  $("remarque-cahier").value = etat.cahier.remarque || "";
  listeConstats($("constats-page"), p.constats);
  listeConstats($("constats-cahier"), etat.cahier.constats);
}

function probleme(p, nom) {
  // le choix fait à la main l'emporte sur la détection
  return nom in p.problemes ? p.problemes[nom] : p.problemes_auto.includes(nom);
}

async function qualifier(champ, valeur, page = etat.page) {
  const p = pageCourante();
  try {
    await api("/api/qualifier", { fichier: etat.cahier.fichier, page, champ, valeur });
  } catch (e) {
    message(`Échec : ${e.message}`);
    dessinerInfos();
    return;
  }
  if (page === 0) etat.cahier.remarque = valeur;
  else if (champ === "type") p.type_verifie = valeur;
  else if (champ === "remarque") p.remarque = valeur;
  else p.problemes[champ] = valeur;
  if (champ === "remarque") {
    // ne pas redessiner : on écraserait une saisie en cours dans l'autre champ
    message("Remarque enregistrée");
    return;
  }
  dessinerInfos();
  marquerVignette();
}

$("type-verifie").addEventListener("change", (ev) => qualifier("type", ev.target.value || null));
$("remarque-page").addEventListener("change", (ev) => qualifier("remarque", ev.target.value));
$("remarque-cahier").addEventListener("change", (ev) => qualifier("remarque", ev.target.value, 0));
$("voir-ocr").addEventListener("change", () => etat.cahier && dessinerCalques());

// ---------- file de chargement des images ----------
//
// Les pages du cahier se chargent à l'approche de la vue. La file charge, dans
// l'ordre : les prochaines pages de la liste à revoir, puis les vignettes, de la page courante vers l'extérieur. Au plus
// trois images à la fois, pour qu'une page demandée ne fasse jamais la queue.

const PAS_LARGEUR = 100; // comme le serveur : même URL, même cache
const SIMULTANES = 3;
const chargeur = { file: [], enCours: new Set(), charges: new Set() };

function urlImage(fichier, page, largeurPixels) {
  const pixels = Math.round(largeurPixels * (window.devicePixelRatio || 1) / PAS_LARGEUR) * PAS_LARGEUR;
  return `/api/image?fichier=${encodeURIComponent(fichier)}&page=${page}&largeur=${Math.max(PAS_LARGEUR, pixels)}`;
}

function pomper() {
  while (chargeur.enCours.size < SIMULTANES && chargeur.file.length) {
    const { url, cible } = chargeur.file.shift();
    if (chargeur.charges.has(url)) { if (cible) cible.src = url; continue; }
    if (chargeur.enCours.has(url)) continue;
    chargeur.enCours.add(url);
    const img = new Image();
    img.onload = img.onerror = () => {
      chargeur.enCours.delete(url);
      chargeur.charges.add(url);
      if (cible) cible.src = url; // déjà en cache : affichage immédiat
      pomper();
    };
    img.src = url;
  }
}

function planifier() {
  // remplace la file : ce qui n'est pas encore parti est réordonné
  const fichier = etat.cahier.fichier;
  const n = etat.page;
  const total = etat.cahier.pages.length;
  const grande = largeurAffichee();
  const file = [];
  if (etat.liste) {
    for (const e of etat.liste.elements.slice(etat.index + 1, etat.index + 4)) {
      file.push({ url: urlImage(e.fichier, e.page, grande) });
    }
  }
  for (let d = 0; d < total; d += 1) {
    for (const p of d ? [n + d, n - d] : [n]) {
      const img = etat.vignettes.get(p);
      if (img && !img.getAttribute("src")) {
        file.push({ url: `/api/image?fichier=${encodeURIComponent(fichier)}&page=${p}&largeur=200`, cible: img });
      }
    }
  }
  chargeur.file = file;
  pomper();
}

// ---------- vignettes ----------

function dessinerVignettes() {
  const bande = $("vignettes");
  bande.replaceChildren();
  etat.vignettes = new Map();
  for (const p of etat.cahier.pages) {
    const v = element("div", { class: "vignette" + (p.service ? " service" : ""), title: `Page ${p.page} ${p.type}` });
    v.dataset.page = p.page;
    // pas de src : la file de chargement la donne, après la page à voir
    const img = element("img", { alt: "", width: Math.round((96 * p.largeur) / p.hauteur), height: 96 });
    etat.vignettes.set(p.page, img);
    v.append(
      img,
      element("span", { class: "legende" }, `${p.page}${TYPES[p.type] ? " · " + TYPES[p.type] : ""}`),
    );
    v.addEventListener("click", () => allerPage(p.page));
    bande.append(v);
  }
}

function marquerVignette() {
  const compte = new Map();
  for (const n of etat.cahier.notes) compte.set(n.page, (compte.get(n.page) || 0) + 1);
  for (const v of $("vignettes").children) {
    const page = Number(v.dataset.page);
    const s = etat.statuts.get(cle(etat.cahier.fichier, page));
    v.classList.toggle("courant", page === etat.page);
    v.classList.toggle("vue", s === "vue");
    v.classList.toggle("a_revoir", s === "a_revoir");
    v.querySelector(".compte")?.remove();
    v.querySelector(".alerte")?.remove();
    const p = etat.cahier.pages[page - 1];
    const problemes = etat.problemes.filter((nom) => probleme(p, nom));
    if (problemes.length + p.constats.length) {
      v.append(element("span", { class: "alerte", title: [...problemes, ...p.constats].join("\n") }, "⚠"));
    }
    const legende = v.querySelector(".legende");
    const type = p.type_verifie || p.type;
    legende.textContent = `${page}${TYPES[type] ? " · " + TYPES[type] : ""}${p.type_verifie ? " ✓" : ""}`;
    if (compte.get(page)) v.append(element("span", { class: "compte" }, String(compte.get(page))));
    if (page === etat.page) v.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
}

// ---------- listes à revoir ----------

async function chargerListes() {
  const listes = await api("/api/listes");
  const choix = $("choix-liste");
  choix.replaceChildren(element("option", { value: "" }, "— aucune —"),
    ...listes.map((l) => element("option", { value: l.nom }, `${l.titre} (${l.elements})`)));
}

async function rechargerStatuts() {
  // les statuts dépendent de la tâche de la liste ouverte : on repart de zéro
  etat.statuts = new Map();
  for (const [f, p, s] of await api(`/api/statuts?tache=${tache()}`)) etat.statuts.set(cle(f, p), s);
  if (etat.cahier) { dessinerStatut(); dessinerInfos(); marquerVignette(); }
}

async function choisirListe(nom, index = 0) {
  if (!nom) {
    etat.liste = null;
    etat.index = -1;
    $("accepter").hidden = false;
    adapterEtiquettes();
    await rechargerStatuts();
    $("consigne").textContent = "";
    dessinerElements();
    if (etat.cahier) rafraichirPage();
    return;
  }
  etat.liste = { nom, ...(await api(`/api/liste?nom=${encodeURIComponent(nom)}`)) };
  await rechargerStatuts();
  $("consigne").textContent = etat.liste.consigne || "";
  $("accepter").hidden = aMasquer();
  adapterEtiquettes();
  dessinerElements();
  if (etat.liste.elements.length) await allerElement(Math.min(index, etat.liste.elements.length - 1));
}

async function allerElement(i) {
  if (!etat.liste || !etat.liste.elements.length) return;
  etat.index = Math.min(Math.max(0, i), etat.liste.elements.length - 1);
  const e = etat.liste.elements[etat.index];
  const y = (e.marques || [])[0]?.y0;
  if (!etat.cahier || etat.cahier.fichier !== e.fichier) await ouvrirCahier(e.fichier, e.page, y);
  else allerPage(e.page, y);
  dessinerElements();
}

function dessinerElements() {
  const ol = $("elements");
  ol.replaceChildren();
  if (!etat.liste) { $("progression").textContent = ""; return; }
  let vues = 0;
  etat.liste.elements.forEach((e, i) => {
    const s = etat.statuts.get(cle(e.fichier, e.page));
    if (s) vues += 1;
    const li = element("li", { class: i === etat.index ? "courant" : "", title: e.commentaire || "" });
    li.append(element("span", { class: `pastille ${s || ""}` }),
      element("span", { class: "nom" }, `${nomCourt(e.fichier)} p. ${e.page}`));
    li.addEventListener("click", () => allerElement(i));
    ol.append(li);
  });
  $("progression").textContent = `${vues} / ${etat.liste.elements.length} pages traitées`;
  ol.querySelector(".courant")?.scrollIntoView({ block: "nearest" });
}

$("choix-liste").addEventListener("change", (ev) => choisirListe(ev.target.value));
$("elem-prec").addEventListener("click", () => allerElement(etat.index - 1));
$("elem-suiv").addEventListener("click", () => allerElement(etat.index + 1));
$("accepter").addEventListener("click", () => accepterMarques());

// ---------- recherche d'un cahier ----------

let minuterieRecherche;
$("champ-cahier").addEventListener("input", (ev) => {
  clearTimeout(minuterieRecherche);
  const motif = ev.target.value.trim();
  minuterieRecherche = setTimeout(async () => {
    if (motif.length < 3) return;
    const noms = await api(`/api/cahiers?q=${encodeURIComponent(motif)}`);
    $("propositions").replaceChildren(...noms.map((n) => element("option", { value: n })));
    if (noms.includes(motif)) ouvrirCahier(motif);
  }, 200);
});
$("recherche").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const motif = $("champ-cahier").value.trim();
  const noms = await api(`/api/cahiers?q=${encodeURIComponent(motif)}`);
  if (noms.length) ouvrirCahier(noms.includes(motif) ? motif : noms[0]);
  else message("Aucun cahier ne correspond");
});

// ---------- navigation, zoom, clavier ----------

$("page-prec").addEventListener("click", () => allerPage(etat.page - 1));
$("page-suiv").addEventListener("click", () => allerPage(etat.page + 1));
$("champ-page").addEventListener("change", (ev) => allerPage(Number(ev.target.value)));

function zoomer(facteur) {
  if (!etat.cahier) return;
  etat.zoom = facteur === null ? null
    : Math.min(3000, Math.max(300, Math.round(largeurAffichee() * facteur)));
  dimensionner();
  allerPage(etat.page);
}
$("zoom-plus").addEventListener("click", () => zoomer(1.25));
$("zoom-moins").addEventListener("click", () => zoomer(0.8));
$("zoom-ajuster").addEventListener("click", () => zoomer(null));
$("pivoter").addEventListener("click", () => pivoter());
$("voir-marques").addEventListener("change", () => etat.cahier && dessinerCalques());
async function choisirEtiquette(nom) {
  $("etiquette").value = nom;
  try { localStorage.setItem("etiquette", nom); } catch { /* sans stockage */ }
  // une note ouverte prend aussi la nouvelle étiquette
  const note = etat.note && etat.cahier.notes.find((n) => n.id === etat.note);
  if (note && note.etiquette !== nom) {
    await api("/api/notes/modifier", { id: note.id, etiquette: nom });
    note.etiquette = nom;
    if (!$("formulaire-note").hidden) $("note-etiquette").value = nom;
    message(`Note : ${nom}`);
    rafraichirPage();
    return;
  }
  message(`Étiquette : ${nom}`);
}

function adapterEtiquettes() {
  // à l'ouverture d'une liste : numéros des raccourcis, et dans une liste à
  // masquer, une étiquette de donnée personnelle
  let choisie = $("etiquette").value;
  if (aMasquer() && !etat.groupes[PERSONNELLES].includes(choisie)) {
    choisie = etat.groupes[PERSONNELLES].at(-1);
  }
  remplirEtiquettes($("etiquette"), choisie);
}

$("etiquette").addEventListener("change", (ev) => {
  try { localStorage.setItem("etiquette", ev.target.value); } catch { /* sans stockage */ }
});

let minuterieTaille;
window.addEventListener("resize", () => {
  clearTimeout(minuterieTaille);
  minuterieTaille = setTimeout(() => { if (etat.cahier && etat.zoom === null) { dimensionner(); allerPage(etat.page); } }, 200);
});

document.addEventListener("keydown", async (ev) => {
  if (ev.key === "Escape") { fermerFormulaire(); if (etat.cahier) rafraichirPage(); return; }
  if (ev.target.closest("input, textarea, select") || ev.ctrlKey || ev.metaKey || ev.altKey) return;
  const actions = {
    ArrowLeft: () => allerPage(etat.page - 1),
    ArrowRight: () => allerPage(etat.page + 1),
    n: () => allerElement(etat.index + 1),
    p: () => allerElement(etat.index - 1),
    v: async () => {
      await poserStatut("vue", false);
      if (etat.liste) allerElement(etat.index + 1); else allerPage(etat.page + 1);
    },
    r: () => poserStatut("a_revoir"),
    "+": () => zoomer(1.25),
    "=": () => zoomer(1.25),
    "-": () => zoomer(0.8),
    "0": () => zoomer(null),
    t: () => pivoter(),
    a: () => accepterMarques(),
    Delete: () => supprimerNote(),
    Backspace: () => supprimerNote(),
    m: () => { $("voir-marques").checked = !$("voir-marques").checked; if (etat.cahier) dessinerCalques(); },
    ...Object.fromEntries(raccourcis().map((nom, i) => [String(i + 1), () => choisirEtiquette(nom)])),
  };
  if (actions[ev.key]) { ev.preventDefault(); await actions[ev.key](); }
});

// ---------- démarrage ----------

(async () => {
  ({ etiquettes: etat.groupes, problemes: etat.problemes, types: etat.types } = await api("/api/etiquettes"));
  etat.etiquettes = Object.values(etat.groupes).flat();
  $("type-verifie").append(...etat.types.map((t) => element("option", { value: t }, t)));
  let preferee;
  try {
    preferee = localStorage.getItem("etiquette");
    etat.rotations = new Map(JSON.parse(localStorage.getItem("rotations") || "[]"));
  } catch { /* sans stockage */ }
  remplirEtiquettes($("etiquette"), etat.etiquettes.includes(preferee) ? preferee : undefined);
  await chargerListes();
  await lireAdresse();
})();
