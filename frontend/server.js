/**
 * server.js
 *
 * This server uses Express to serve your production build over HTTPS.
 * It also proxies API calls (routes starting with /api) to your backend at https://54.86.99.85:5000.
 *
 * For production use, ensure you have valid SSL certificate and key files.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

// Create the Express application.
const app = express();

// Define the path to your build folder.
const buildPath = path.join(__dirname, 'build');

// Serve static files from the build folder.
app.use(express.static(buildPath));

// Proxy API requests with /api prefix without rewriting.
app.use('/api', createProxyMiddleware({
  target: 'https://54.86.99.85:5000/api', // Backend URL
  changeOrigin: true,
  secure: true, // Set to false if using self-signed certificates on the backend
  logLevel: 'debug'
}));

// For any other route, send back the index.html (for SPA routing).
app.get('*', (req, res) => {
  res.sendFile(path.join(buildPath, 'index.html'));
});

// Read SSL certificate and key files.
// Adjust the paths if needed.
const sslOptions = {
  key: fs.readFileSync(path.join(__dirname, 'ssl', 'privkey-rsa.pem')),
  cert: fs.readFileSync(path.join(__dirname, 'ssl', 'fullchain-rsa.pem'))
};

// Set the port; default to 3000 (or any port you prefer).
const PORT = process.env.PORT || 3000;

// Create and start the HTTPS server.
https.createServer(sslOptions, app).listen(PORT, () => {
  console.log(`HTTPS server running on port ${PORT}`);
});
