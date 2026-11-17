// Carrousels : boutons précédent / suivant et pastilles de pagination.
// Le défilement reste natif (scroll-snap) : sans JS, la piste défile au doigt
// ou à la molette.
document.querySelectorAll("[data-carousel]").forEach((carousel) => {
  const track = carousel.querySelector(".carousel__track");
  const items = [...track.children];
  const prev = carousel.querySelector("[data-carousel-prev]");
  const next = carousel.querySelector("[data-carousel-next]");
  const dotsBox = carousel.querySelector(".carousel__dots");
  if (!items.length) return;

  const dots = items.map((_, i) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.className = "carousel__dot";
    dot.setAttribute("aria-label", `Aller à l'élément ${i + 1}`);
    dot.addEventListener("click", () => goTo(i));
    dotsBox?.append(dot);
    return dot;
  });

  // La piste est en position: relative, donc offsetLeft est relatif à elle.
  const start = (item) => item.offsetLeft - items[0].offsetLeft;

  const current = () => {
    let best = 0;
    items.forEach((item, i) => {
      if (Math.abs(start(item) - track.scrollLeft) < Math.abs(start(items[best]) - track.scrollLeft)) best = i;
    });
    return best;
  };

  const goTo = (i) => {
    const target = items[Math.max(0, Math.min(i, items.length - 1))];
    track.scrollTo({ left: start(target) });
  };

  const update = () => {
    const i = current();
    dots.forEach((dot, j) => dot.setAttribute("aria-current", String(i === j)));
    const max = track.scrollWidth - track.clientWidth;
    if (prev) prev.disabled = track.scrollLeft <= 1;
    if (next) next.disabled = track.scrollLeft >= max - 1;
  };

  prev?.addEventListener("click", () => goTo(current() - 1));
  next?.addEventListener("click", () => goTo(current() + 1));
  track.addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
  window.addEventListener("resize", update);
  update();
});
