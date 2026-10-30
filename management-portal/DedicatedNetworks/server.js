require('dotenv').config();

const express = require('express');
const path    = require('path');

const areasRouter    = require('./routes/areas');
const networksRouter = require('./routes/networks');
const accessesRouter = require('./routes/accesses');
const profilesRouter = require('./routes/profiles');
const sessionsRouter = require('./routes/sessions');
const webhooksRouter = require('./routes/webhooks');
const configRouter   = require('./routes/config');

const app  = express();
const PORT = process.env.PORT || 3555;

// ── Middleware ──────────────────────────────────────────────
app.use(express.json({ type: ['application/json', 'application/cloudevents+json', 'application/*+json'] }));

// Request logger
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// ── API Routes ──────────────────────────────────────────────
app.use('/api/areas',    areasRouter);
app.use('/api/networks', networksRouter);
app.use('/api/accesses', accessesRouter);
app.use('/api/profiles', profilesRouter);
app.use('/api/sessions', sessionsRouter);
app.use('/webhooks',     webhooksRouter);  // CAMARA posts here
app.use('/api/webhooks', webhooksRouter);  // frontend polls here
app.use('/api/config',   configRouter);

// ── Health check ────────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    port: PORT,
    env: {
      areas:    !!process.env.AREAS_URL,
      networks: !!process.env.NETWORKS_URL,
      profiles: !!process.env.PROFILES_URL,
      accesses: !!process.env.ACCESSES_URL,
      qod:      !!process.env.QOD_URL,
      sink:     process.env.SINK_BASE_URL || '(not set)'
    }
  });
});

// ── Sandbox reachability check ───────────────────────────────
app.get('/api/sandbox-health', async (req, res) => {
  const { apiRequest } = require('./services/apiService');
  const checks = [
    { key: 'areas',    url: `${process.env.AREAS_URL}/retrieve-service-areas`,   method: 'POST', body: {} },
    { key: 'networks', url: `${process.env.NETWORKS_URL}/networks` },
    { key: 'accesses', url: `${process.env.ACCESSES_URL}/accesses` },
    { key: 'profiles', url: `${process.env.PROFILES_URL}/profiles` },
  ];
  const results = await Promise.all(checks.map(async ({ key, url, method = 'GET', body }) => {
    try {
      const r = await apiRequest(url, { method, body });
      return { key, ok: r.status < 500, status: r.status };
    } catch (e) {
      return { key, ok: false, status: null };
    }
  }));
  const out = {};
  results.forEach(r => { out[r.key] = { ok: r.ok, status: r.status }; });
  res.json(out);
});

// ── Serve portal (must come after API routes) ───────────────
app.use(express.static(path.join(__dirname, 'public')));

// Fallback: serve index.html for any unmatched route
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// ── Error handler ───────────────────────────────────────────
app.use((err, req, res, next) => {
  console.error('[error]', err);
  res.status(500).json({ error: 'Internal server error', message: err.message });
});

app.listen(PORT, () => {
  console.log('');
  console.log('  5G-MAG · CAMARA Dedicated Networks Portal');
  console.log('  ──────────────────────────────────────────');
  console.log(`  Portal  →  http://localhost:${PORT}`);
  console.log(`  Health  →  http://localhost:${PORT}/health`);
  console.log(`  Sink    →  ${process.env.SINK_BASE_URL || '(SINK_BASE_URL not set in .env)'}`);
  console.log('');
});
