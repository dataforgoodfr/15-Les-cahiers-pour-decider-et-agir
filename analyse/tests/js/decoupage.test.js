// Découpage de l'outil d'annotation : node --test tests/js
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { decouper: decouperAvecIds, MARGE } = require("../../annotation/statique/decoupage.js");

// les cadres sans l'identifiant du début, sauf où on le vérifie
const decouper = (pages, notes) => new Map([...decouperAvecIds(pages, notes)].map(
  ([n, cadres]) => [n, cadres.map(({ debut, ...cadre }) => cadre)],
));

const page = (n, largeur = 600, hauteur = 800, double = null) => ({ page: n, largeur, hauteur, double });
const debut = (n, x, y) => ({ id: `d${n}-${y}`, page: n, debut: true, x, y });
const fin = (n, x, y) => ({ page: n, debut: false, x, y });

test("un début et une fin près des bords couvrent la largeur", () => {
  const cadres = decouper([page(1)], [debut(1, 40, 200), fin(1, 560, 400)]);
  assert.deepEqual(cadres.get(1), [{ contribution: 1, x0: 0, y0: 200 - MARGE, x1: 600, y1: 400 + MARGE }]);
});

test("une case de grille garde ses côtés", () => {
  const cadres = decouper([page(1)], [debut(1, 200, 200), fin(1, 360, 300)]);
  assert.deepEqual(cadres.get(1), [{ contribution: 1, x0: 200 - MARGE, y0: 200 - MARGE, x1: 360 + MARGE, y1: 300 + MARGE }]);
});

test("sur plusieurs pages, les pages du milieu sont pleines", () => {
  const cadres = decouper([page(1), page(2), page(3)], [debut(1, 40, 30), fin(3, 560, 790)]);
  assert.deepEqual(cadres.get(1), [{ contribution: 1, x0: 0, y0: 0, x1: 600, y1: 800 }]);
  assert.deepEqual(cadres.get(2), [{ contribution: 1, x0: 0, y0: 0, x1: 600, y1: 800 }]);
  assert.deepEqual(cadres.get(3), [{ contribution: 1, x0: 0, y0: 0, x1: 600, y1: 800 }]);
});

test("sans fin notée, pas de contour", () => {
  const cadres = decouper([page(1)], [debut(1, 40, 200), debut(1, 40, 500), fin(1, 560, 600)]);
  // la première s'arrêterait au début suivant : seule la seconde a sa fin
  assert.deepEqual(cadres.get(1), [{ contribution: 2, x0: 0, y0: 500 - MARGE, x1: 600, y1: 600 + MARGE }]);
});

test("une double page se lit à gauche puis à droite", () => {
  // Firminy p. 43 : la fin de gauche est plus bas que le début de droite
  const pages = [page(42), page(43, 840, 600)];
  const cadres = decouper(pages, [debut(42, 40, 663), debut(43, 438, 72), fin(43, 346, 96), fin(43, 797, 210)]);
  const coupure = 438 - MARGE;
  assert.deepEqual(cadres.get(43), [
    { contribution: 1, x0: 0, y0: 0, x1: 346 + MARGE, y1: 96 + MARGE },
    { contribution: 2, x0: coupure, y0: 72 - MARGE, x1: 840, y1: 210 + MARGE },
  ]);
});

test("un cadre connaît la note de début de sa contribution", () => {
  const cadres = decouperAvecIds([page(1)], [debut(1, 40, 200), fin(1, 560, 400)]);
  assert.equal(cadres.get(1)[0].debut, "d1-200");
});
