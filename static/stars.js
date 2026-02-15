(function () {
  "use strict";

  const canvas = document.getElementById("starfield");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let w, h, stars, dpr;

  function resize() {
    dpr = window.devicePixelRatio || 1;
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // Create stars with varied brightness and twinkle speeds
  function createStars() {
    const count = Math.min(300, Math.floor((w * h) / 3000));
    stars = [];

    for (let i = 0; i < count; i++) {
      const isMilkyWay = Math.random() < 0.35;
      let x, y;

      if (isMilkyWay) {
        // Cluster stars along a diagonal band (milky way)
        const t = Math.random();
        const bandX = t * w * 1.4 - w * 0.2;
        const bandY = t * h * 0.6 - h * 0.1;
        const spread = 80 + Math.random() * 120;
        x = bandX + (Math.random() - 0.5) * spread;
        y = bandY + (Math.random() - 0.5) * spread;
      } else {
        x = Math.random() * w;
        y = Math.random() * h;
      }

      stars.push({
        x: x,
        y: y,
        baseRadius: isMilkyWay
          ? 0.3 + Math.random() * 0.8
          : 0.4 + Math.random() * 1.2,
        baseAlpha: isMilkyWay
          ? 0.15 + Math.random() * 0.35
          : 0.2 + Math.random() * 0.6,
        twinkleSpeed: 0.3 + Math.random() * 1.5,
        twinkleOffset: Math.random() * Math.PI * 2,
        // A few bright stars get a subtle blue/white tint
        color: Math.random() < 0.1
          ? `rgba(180, 210, 255, `
          : `rgba(255, 255, 255, `,
      });
    }
  }

  function draw(time) {
    ctx.clearRect(0, 0, w, h);
    const t = time * 0.001;

    for (let i = 0; i < stars.length; i++) {
      const s = stars[i];
      const twinkle = Math.sin(t * s.twinkleSpeed + s.twinkleOffset);
      const alpha = s.baseAlpha + twinkle * 0.2;
      const radius = s.baseRadius + twinkle * 0.15;

      if (alpha <= 0 || radius <= 0) continue;

      ctx.beginPath();
      ctx.arc(s.x, s.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = s.color + Math.max(0, Math.min(1, alpha)) + ")";
      ctx.fill();
    }

    requestAnimationFrame(draw);
  }

  resize();
  createStars();
  requestAnimationFrame(draw);

  window.addEventListener("resize", function () {
    resize();
    createStars();
  });
})();
