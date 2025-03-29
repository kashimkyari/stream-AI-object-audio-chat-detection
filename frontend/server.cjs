/**
 * server.js
 *
 * A simple HTTPS server using Express to serve your production build.
 * Requires SSL certificate and key files (e.g. ssl/server.cert and ssl/server.key).
 */

const https = require('https');
const express = require('express');
const fs = require('fs');
const path = require('path');

// Create the Express app.
const app = express();

// Path to your production build folder (adjust if needed)
const buildPath = path.join(__dirname, 'build');

// Serve static files from the build directory.
app.use(express.static(buildPath));

// For any other request, send back index.html (for SPA routing).
app.get('*', (req, res) => {
  res.sendFile(path.join(buildPath, 'index.html'));
});

// Read SSL certificate and key files.
const sslOptions = {
  key: fs.readFileSync(path.join(__dirname, 'ssl', './home/ec2-user/certs/fullchain-rsa.pem')),
  cert: fs.readFileSync(path.join(__dirname, 'ssl', './home/ec2-user/certs/privkey-rsa.pem')),
};

// Set the port; default to 443 for HTTPS.
const PORT = process.env.PORT || 443;

// Create HTTPS server.
https.createServer(sslOptions, app).listen(PORT, () => {
  console.log(`HTTPS server running on port ${PORT}`);
});
