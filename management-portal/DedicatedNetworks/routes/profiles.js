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
const router = express.Router();

const PROFILES_BASE = () => (process.env.PROFILES_URL || '').replace(/\/+$/, '');
const QOD_BASE      = () => {
  const url = (process.env.QOD_URL || '').replace(/\/+$/, '');
  return url.includes('undefined') ? '' : url;   // placeholder counts as unset
};

// GET /api/profiles/network  ->  GET {{ profiles_url }}/profiles
router.get('/network', async (req, res) => {
  try {
    const result = await apiRequest(`${PROFILES_BASE()}/profiles`, { method: 'GET' });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// GET /api/profiles/network/:profileId  ->  GET {{ profiles_url }}/profiles/:profileId
router.get('/network/:profileId', async (req, res) => {
  try {
    const result = await apiRequest(`${PROFILES_BASE()}/profiles/${req.params.profileId}`, { method: 'GET' });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// GET /api/profiles/qos  ->  POST {{ qod_url }}/retrieve-qos-profiles (no device filter = all profiles)
router.get('/qos', async (req, res) => {
  if (!QOD_BASE()) {
    return res.status(503).json({ error: 'QoS profiles need a Quality on Demand API; QOD_URL is not set.' });
  }
  try {
    const result = await apiRequest(`${QOD_BASE()}/retrieve-qos-profiles`, {
      method: 'POST',
      body: {}   // no device filter — returns all available profiles
    });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

// GET /api/profiles/qos/:name  ->  GET {{ qod_url }}/qos-profiles/:name
router.get('/qos/:name', async (req, res) => {
  if (!QOD_BASE()) {
    return res.status(503).json({ error: 'QoS profiles need a Quality on Demand API; QOD_URL is not set.' });
  }
  try {
    const result = await apiRequest(`${QOD_BASE()}/qos-profiles/${req.params.name}`, { method: 'GET' });
    res.status(result.status).json(result.data);
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

module.exports = router;
