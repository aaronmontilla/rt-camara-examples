/*
License: 5G-MAG Public License (v1.0)
Author: Jordi Joan Gimenez
Copyright: (C) 2026 5G-MAG Association

For full license terms please see the LICENSE file distributed with this
program. If this file is missing then the license can be retrieved from
https://hub.5g-mag.com/Getting-Started/OFFICIAL_5G-MAG_Public_License_v1.0.pdf
*/

const express = require('express');
const { apiRequest } = require('../services/apiService');
const { sinkFields } = require('../services/webhookService');
const router = express.Router();

const BASE = () => process.env.ACCESSES_URL;

// GET /api/accesses
router.get('/', async (req, res) => {
  try {
    const url = new URL(`${BASE()}/accesses`);
    if (req.query.networkId) url.searchParams.set('networkId', req.query.networkId);
    const result = await apiRequest(url.toString(), { method: 'GET' });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// POST /api/accesses
router.post('/', async (req, res) => {
  try {
    const body = { ...req.body };
    Object.assign(body, sinkFields('accesses', req.body));
    console.log('[CREATE ACCESS] body sent to API:', JSON.stringify(body, null, 2));
    const result = await apiRequest(`${BASE()}/accesses`, { method: 'POST', body });
    console.log('[CREATE ACCESS] API response status:', result.status, JSON.stringify(result.data));
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// GET /api/accesses/:accessId
router.get('/:accessId', async (req, res) => {
  try {
    const result = await apiRequest(`${BASE()}/accesses/${req.params.accessId}`, { method: 'GET' });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// DELETE /api/accesses/:accessId
router.delete('/:accessId', async (req, res) => {
  try {
    const result = await apiRequest(`${BASE()}/accesses/${req.params.accessId}`, { method: 'DELETE' });
    res.status(result.status).json(result.data || {});
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// GET /api/accesses/:accessId/devices
router.get('/:accessId/devices', async (req, res) => {
  try {
    const url = new URL(`${BASE()}/accesses/${req.params.accessId}/devices`);
    if (req.query.perPage) url.searchParams.set('perPage', req.query.perPage);
    if (req.query.seek) url.searchParams.set('seek', req.query.seek);
    if (req.query.deviceStatus) url.searchParams.set('deviceStatus', req.query.deviceStatus);
    const result = await apiRequest(url.toString(), { method: 'GET' });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// POST /api/accesses/:accessId/devices/add
router.post('/:accessId/devices/add', async (req, res) => {
  try {
    console.log('[ADD DEVICE] body sent to API:', JSON.stringify(req.body, null, 2));
    const result = await apiRequest(`${BASE()}/accesses/${req.params.accessId}/devices/add`, {
      method: 'POST', body: req.body
    });
    console.log('[ADD DEVICE] API response:', result.status, JSON.stringify(result.data));
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// POST /api/accesses/:accessId/devices/remove
router.post('/:accessId/devices/remove', async (req, res) => {
  try {
    const result = await apiRequest(`${BASE()}/accesses/${req.params.accessId}/devices/remove`, {
      method: 'POST', body: req.body
    });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

module.exports = router;
