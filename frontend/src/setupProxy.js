const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: "https://127.0.0.1:5000", // Update with your Elastic IP
      changeOrigin: true,
      secure: false,
    })
  );
};
