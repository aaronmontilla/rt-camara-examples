/*
License: 5G-MAG Public License (v1.0)
Author: Jordi Joan Gimenez
Copyright: (C) 2026 5G-MAG Association

For full license terms please see the LICENSE file distributed with this
program. If this file is missing then the license can be retrieved from
https://hub.5g-mag.com/Getting-Started/OFFICIAL_5G-MAG_Public_License_v1.0.pdf
*/

const express = require('express');
const { storeNotification, getNotifications, clearNotifications, sinkToken } = require('../services/webhookService');
const router = express.Router();

// CAMARA APIs POST CloudEvents to /webhooks/:resource, with the sinkCredential
// we registered sent as "Authorization: Bearer <token>". Reply 204, no body.
// e.g. /webhooks/networks, /webhooks/accesses, /webhooks/sessions
router.post('/:resource', (req, res) => {
  const auth = req.get('authorization') || '';
  if (auth !== `Bearer ${sinkToken()}`) {
    return res.status(401).json({ status: 401, code: 'UNAUTHENTICATED', message: 'Missing or invalid sink credential.' });
  }
  storeNotification(req.params.resource, req.body);
  res.status(204).end();
});

// Frontend polls this to see incoming notifications
// GET /api/webhooks/notifications?source=networks
router.get('/notifications', (req, res) => {
  const notifications = getNotifications(req.query.source || null);
  res.json(notifications);
});

// DELETE /api/webhooks/notifications - clear all
router.delete('/notifications', (req, res) => {
  clearNotifications();
  res.json({ cleared: true });
});

module.exports = router;
