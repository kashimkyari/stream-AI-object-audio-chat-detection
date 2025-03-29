/**
 * server.js
 *
 * Serves the production build over HTTPS and proxies API requests
 * to the backend running at https://54.86.99.85:5000.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const buildPath = path.join(__dirname, 'build');

// Serve static files from the build folder.
app.use(express.static(buildPath));

// Proxy API requests (without rewriting the path).
app.use('/api', createProxyMiddleware({
  target: 'https://127.0.0.1:5000',
  changeOrigin: true,
  secure: true, // set to false if your backend uses self-signed certs
  logLevel: 'debug'
}));

// For all other routes, serve index.html (for SPA routing).
app.get('*', (req, res) => {
  res.sendFile(path.join(buildPath, 'index.html'));
});

// SSL options: replace these paths with your actual certificate and key.
const sslOptions = {
  key: fs.readFileSync(path.join(__dirname, 'ssl', 'privkey-rsa.pem')),
  cert: fs.readFileSync(path.join(__dirname, 'ssl', 'fullchain-rsa.pem'))
};

const PORT = process.env.PORT || 3000;

https.createServer(sslOptions, app).listen(PORT, () => {
  console.log(`HTTPS server running on port ${PORT}`);
});





