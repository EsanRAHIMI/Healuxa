// Expo's default Metro config already understands npm workspaces (watchFolders + node_modules lookup).
const { getDefaultConfig } = require('expo/metro-config');

module.exports = getDefaultConfig(__dirname);
