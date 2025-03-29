const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
    app.use(
        '/api',
        createProxyMiddleware({
            target: 'https://54.86.99.85:5000',
            changeOrigin: true,
            secure: false,  // Allow self-signed SSL certificates
        })
    );
};
