import { resolve } from "node:path";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

// Bundles everything (JS, CSS, Leaflet) into one self-contained HTML file,
// output at ui/dist/area_picker.html — the path camara/ui.py serves as the
// ui://camara/area-picker resource.
export default defineConfig({
  plugins: [viteSingleFile()],
  build: {
    outDir: resolve(__dirname, "../dist"),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, "area_picker.html"),
    },
  },
});
