// Module-level singleton — shared across all SingleImage instances in this tab.
// All images register here and are released one at a time at INTERVAL_MS.
const queue = []; // [{setSrc, url}]
let intervalId = null;

const INTERVAL_MS = 150;

function startInterval() {
  if (intervalId !== null) return;
  intervalId = setInterval(() => {
    const next = queue.shift();
    if (next) {
      next.setSrc(next.url);
    }
    if (queue.length === 0) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }, INTERVAL_MS);
}

/**
 * Flush all pending entries and stop the interval.
 * Call this when a new gene search starts so stale loads don't bleed in.
 */
export function resetQueue() {
  queue.length = 0;
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

/**
 * Returns an enqueue function. Each SingleImage calls:
 *   const dequeue = enqueue(setSrc, url)
 * on mount, and dequeue() on unmount (removes entry if not yet fired).
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
