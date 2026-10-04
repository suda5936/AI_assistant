import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const fe = path.resolve(here, "../../../frontend");
const nm = (name: string) => path.join(fe, "node_modules", name);

export default {
  root: fe,
  resolve: {
    alias: [
      { find: /^vitest$/, replacement: nm("vitest") },
      { find: /^react$/, replacement: nm("react") },
      { find: /^react\/(.*)$/, replacement: nm("react") + "/$1" },
      { find: /^react-dom$/, replacement: nm("react-dom") },
      { find: /^react-dom\/(.*)$/, replacement: nm("react-dom") + "/$1" },
      { find: /^react-router-dom$/, replacement: nm("react-router-dom") },
      { find: /^@testing-library\/react$/, replacement: nm("@testing-library/react") },
    ],
  },
  server: { fs: { strict: false } },
  test: {
    environment: "jsdom",
    globals: true,
    include: [path.join(here, "t16_*.test.tsx")],
    env: { VITE_API_BASE_URL: "http://127.0.0.1:8016" },
    testTimeout: 30000,
    hookTimeout: 60000,
  },
};
