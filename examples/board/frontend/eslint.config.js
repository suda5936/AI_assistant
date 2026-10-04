import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { react, "react-hooks": reactHooks },
    settings: { react: { version: "18.3" } },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react/no-danger": "error",
      "no-console": "error",
      "no-debugger": "error",
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-globals": ["error", "process"],
    },
  },
  {
    files: ["vite.config.ts"],
    languageOptions: { globals: globals.node },
    rules: { "no-restricted-globals": "off" },
  },
);
