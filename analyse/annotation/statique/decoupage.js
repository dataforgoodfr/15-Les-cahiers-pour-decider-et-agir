// Découpage d'un cahier en contributions, d'après les débuts et fins notés :
// la même règle que `selection.contribution`, pour dessiner les contours.
// Tout est dans le sens de lecture (la page telle qu'affichée), en points.
"use strict";

const MARGE = 6; // points : le début est un point posé sur la première ligne
const CENTRE = [0.35, 0.65]; // part de la largeur où un début ouvre la page de droite
const BORD_X = 0.15; // part de la largeur sous laquelle un bord colle à la page
const BORD_Y = 0.08; // de même pour la hauteur

function coupure(page, debuts) {
  // l'abscisse entre les deux pages d'une double page, null pour une page simple
  const { largeur, hauteur, double } = page;
  const milieu = debuts.filter((x) => x > CENTRE[0] * largeur && x < CENTRE[1] * largeur);
  if (double === false || (double == null && !(largeur > hauteur && milieu.length))) return null;
  return milieu.length ? Math.min(...milieu) - MARGE : largeur / 2;
}

function avant(a, b) {
  // ordre de lecture : page, hauteur (page de droite sous celle de gauche), abscisse
  return a.page - b.page || a.v - b.v || a.x - b.x;
}

// pages : [{page, largeur, hauteur, double}] (largeur et hauteur lues ;
// double : la qualification « double page », null si non tranchée)
// notes : [{id, page, debut, x, y}] (debut : vrai pour un début, faux pour une fin)
// Rend, par page, les cadres {contribution, debut, x0, y0, x1, y1} des contributions
// (debut : l'identifiant de la note de début)
// dont la fin est notée : tant qu'elle ne l'est pas, le contour distrairait.
function decouper(pages, notes) {
  const parPage = new Map(pages.map((p) => [p.page, p]));
  const coupures = new Map(pages.map((p) => [
    p.page,
    coupure(p, notes.filter((n) => n.debut && n.page === p.page).map((n) => n.x)),
  ]));
  const points = notes.filter((n) => parPage.has(n.page)).map((n) => {
    const c = coupures.get(n.page);
    const droite = c !== null && n.x >= c;
    return { ...n, v: n.y + (droite ? parPage.get(n.page).hauteur : 0) };
  });
  const debuts = points.filter((n) => n.debut).sort(avant);
  const fins = points.filter((n) => !n.debut).sort(avant);
  const cadres = new Map(pages.map((p) => [p.page, []]));

  debuts.forEach((debut, i) => {
    const suivant = debuts[i + 1];
    const fin = fins.find((f) => avant(f, debut) >= 0 && (!suivant || avant(f, suivant) <= 0));
    if (!fin) return;
    // bas : hauteur lue (dans l'ordre de lecture) où la contribution s'arrête
    const arret = { page: fin.page, v: fin.v + MARGE, x: fin.x };
    for (let n = debut.page; n <= arret.page; n += 1) {
      const p = parPage.get(n);
      if (!p) continue;
      const c = coupures.get(n);
      const colonnes = c === null ? [[0, p.largeur]] : [[0, c], [c, p.largeur]];
      const haut = n === debut.page ? debut.v - MARGE : 0;
      const bas = n === arret.page ? arret.v : Infinity;
      colonnes.forEach(([g, d], k) => {
        let y0 = Math.max(haut, k * p.hauteur) - k * p.hauteur;
        let y1 = Math.min(bas, (k + 1) * p.hauteur) - k * p.hauteur;
        if (y0 >= y1) return;
        let x0 = g, x1 = d;
        // le début et la fin bornent les côtés de leur colonne ; près du bord,
        // le cadre colle à la page : une page pleine se voit d'un coup d'œil
        const ici = (pt) => pt.page === n && pt.v >= k * p.hauteur && pt.v < (k + 1) * p.hauteur + MARGE;
        if (ici(debut) && debut.x - g > BORD_X * (d - g)) x0 = debut.x - MARGE;
        if (ici(arret) && d - arret.x > BORD_X * (d - g)) x1 = arret.x + MARGE;
        if (y0 < BORD_Y * p.hauteur) y0 = 0;
        if (y1 > (1 - BORD_Y) * p.hauteur) y1 = p.hauteur;
        if (x0 < x1) cadres.get(n).push({ contribution: i + 1, debut: debut.id, x0, y0, x1, y1 });
      });
    }
  });
  return cadres;
}

if (typeof module !== "undefined") module.exports = { decouper, coupure, MARGE };
