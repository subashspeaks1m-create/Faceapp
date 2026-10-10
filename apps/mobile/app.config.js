// EXPO_BASE_URL serves the web build from a sub-path (for example GitHub Pages at /Faceapp).
module.exports = ({ config }) => {
  const baseUrl = process.env.EXPO_BASE_URL;
  if (!baseUrl) return config;
  return { ...config, experiments: { ...config.experiments, baseUrl } };
};
