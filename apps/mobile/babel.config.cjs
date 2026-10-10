// babel-preset-expo adds the react-native-worklets plugin Reanimated 4 needs.
module.exports = function (api) {
  api.cache(true);
  return { presets: ['babel-preset-expo'] };
};
