// Module-level singleton — shared across all SingleImage instances in this tab.
// All images register here and are released one at a time at INTERVAL_MS.
const queue = []; // [{setSrc, url}]
let intervalId = null;

// The grid loads ZFIN's medium variant (~15KB) rather than full-res images
// (~377KB), so releasing them quickly no longer risks flooding the network or
// the backend. Release a small batch per short tick so a comparison grid
// populates almost immediately instead of trickling in at ~7 images/second.
const INTERVAL_MS = 40;
const BATCH_PER_TICK = 4;

function startInterval() {
  if (intervalId !== null) return;
  intervalId = setInterval(() => {
    for (let i = 0; i < BATCH_PER_TICK; i++) {
      const next = queue.shift();
      if (!next) break;
      next.setSrc(next.url);
    }
    if (queue.length === 0) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }, INTERVAL_MS);
}

/**
 * Returns an enqueue function. Each SingleImage calls:
 *   const dequeue = enqueue(setSrc, url)
 * on mount, and dequeue() on unmount (removes entry if not yet fired).
 *
 * Cancellation is per-entry ONLY — cells that leave the grid dequeue their own
 * pending entry in their unmount cleanup. There is deliberately no global
 * flush: one used to run on every comparison change (GEN-50) and it also
 * discarded entries of cells that stayed mounted (adding a gene, narrowing the
 * stage range); those cells never re-enqueued, because their image URL hadn't
 * changed, and sat as empty placeholders until a reload.
 */
export function useImageQueue() {
  function enqueue(setSrc, url) {
    const entry = { setSrc, url };
    queue.push(entry);
    startInterval();

    return function dequeue() {
      const idx = queue.indexOf(entry);
      if (idx !== -1) queue.splice(idx, 1);
    };
  }
  return enqueue;
}
