class ApiCache {
  constructor(freshTTL = 300_000, staleTTL = 1_800_000) {
    this.cache = new Map();
    this.freshTTL = freshTTL;
    this.staleTTL = staleTTL;
    this.inFlight = new Map();
  }

  get(key) {
    const entry = this.cache.get(key);
    if (!entry) return null;
    const age = Date.now() - entry.timestamp;
    if (age < this.freshTTL) return { data: entry.data, status: 'fresh' };
    if (age < this.staleTTL) return { data: entry.data, status: 'stale' };
    this.cache.delete(key);
    return null;
  }

  set(key, data) {
    this.cache.set(key, { data, timestamp: Date.now() });
  }

  async fetch(key, fetcher) {
    const cached = this.get(key);
    if (cached && cached.status === 'fresh') return cached.data;

    if (cached && cached.status === 'stale') {
      this._refresh(key, fetcher);
      return cached.data;
    }

    if (this.inFlight.has(key)) {
      return this.inFlight.get(key);
    }

    const promise = fetcher().then(data => {
      this.set(key, data);
      this.inFlight.delete(key);
      return data;
    }).catch(err => {
      this.inFlight.delete(key);
      throw err;
    });

    this.inFlight.set(key, promise);
    return promise;
  }

  async _refresh(key, fetcher) {
    if (this.inFlight.has(key)) return;
    const promise = fetcher().then(data => {
      this.set(key, data);
      this.inFlight.delete(key);
    }).catch(() => {
      this.inFlight.delete(key);
    });
    this.inFlight.set(key, promise);
  }

  invalidate(key) { this.cache.delete(key); }
  invalidateAll() { this.cache.clear(); }
}

export const apiCache = new ApiCache();
