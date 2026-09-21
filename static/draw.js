"use strict";
window.SnakeBoard = (() => {
const cache = new WeakMap();
function roundRect(ctx, x, y, w, h, radius, fill) {
  ctx.fillStyle = fill; ctx.beginPath(); ctx.roundRect(x, y, w, h, radius); ctx.fill();
}

function draw(canvas, game) {
  const ctx = canvas.getContext("2d");
  const key = JSON.stringify([game.width, game.height, game.body, game.food, game.alive]);
  if (cache.get(canvas) === key) return;
  cache.set(canvas, key);
  canvas.height = Math.round(canvas.width * game.height / game.width);
  canvas.parentElement.style.aspectRatio = `${game.width}/${game.height}`;
  const w = canvas.width, h = canvas.height, cell = w / game.width;
  ctx.fillStyle = "#0c1411"; ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "#1b2821"; ctx.lineWidth = 1;
  for (let x = 0; x <= w; x += cell) { ctx.beginPath(); ctx.moveTo(x + .5, 0); ctx.lineTo(x + .5, h); ctx.stroke(); }
  for (let y = 0; y <= h; y += cell) { ctx.beginPath(); ctx.moveTo(0, y + .5); ctx.lineTo(w, y + .5); ctx.stroke(); }
  if (game.food) {
    const [x, y] = game.food;
    ctx.shadowBlur = 20; ctx.shadowColor = "#ef998066";
    roundRect(ctx, x * cell + cell * .28, y * cell + cell * .28, cell * .44, cell * .44, 5, "#ef9980");
    ctx.shadowBlur = 0;
  }
  for (let i = game.body.length - 1; i >= 0; --i) {
    const [x, y] = game.body[i];
    const ratio = 1 - i / game.body.length;
    const color = i === 0 ? (game.alive ? "#d3f895" : "#ef9980") : `hsl(${92 - ratio * 14} 37% ${25 + ratio * 31}%)`;
    roundRect(ctx, x * cell + 2, y * cell + 2, cell - 4, cell - 4, 6, color);
  }
  const [hx, hy] = game.body[0], [nx, ny] = game.body[1];
  const dx = hx - nx, dy = hy - ny;
  for (const side of [-1, 1]) {
    const ex = hx * cell + cell / 2 + dx * 8 + (dy ? side * 7 : 0);
    const ey = hy * cell + cell / 2 + dy * 8 + (dx ? side * 7 : 0);
    roundRect(ctx, ex - 2, ey - 2, 4, 4, 1, "#18251b");
  }
  canvas.setAttribute("aria-label", `Snake board: score ${game.score}, length ${game.length}, move ${game.ticks}${game.alive ? "" : ", game over"}`);
}

return {draw};
})();
