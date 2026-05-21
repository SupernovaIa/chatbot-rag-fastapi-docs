import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server binds to 0.0.0.0:5173 so it is reachable from outside the container.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});
