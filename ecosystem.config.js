module.exports = {
  apps: [
    {
      name: "kpi-server",
      script: "uv",
      args: "run python -m app.main",
      cwd: __dirname,
      interpreter: "none",
    },
  ],
};
