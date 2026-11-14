import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development (npm run dev) the page is served on port 5173 and
// any /api call is forwarded to the Python server on port 8000.
// In Docker there is no dev server: the built files are served by FastAPI.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
