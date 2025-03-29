const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: "https://54.86.99.85:5000/api", // Update with your Elastic IP
      changeOrigin: true,
      secure: false,
    })
  );
};
