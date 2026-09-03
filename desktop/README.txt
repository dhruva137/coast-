IDR desktop shell (Tauri 2) — SIH 26168 judges' table
=====================================================

A thin native window around the same web console in ../web.
Not Electron. The production binary is a few megabytes and runs offline.

Install (once, on a build machine)
----------------------------------
1. Rust: https://rustup.rs
   On Windows choose the MSVC toolchain (Visual Studio C++ build tools).
2. Node.js + npm (same as the rest of this repo).
3. From this folder:

     npm install

Development
-----------
Start the Vite app first (it listens on port 26168). From the repo root:

     npm install
     npm run dev

Then, from desktop/:

     npm run tauri dev

Tauri loads http://localhost:26168. Do not start `tauri dev` before the
web server — venue wifi is irrelevant here, but the local Vite process is not.

Offline / judges' table (production)
------------------------------------
Venue wifi may be absent. The production build embeds ../../web/dist
(the Vite output) into the binary. No network, no API keys, no backend.

  From the repo root:   npm run build
  From desktop/:        npm run build

Windows artefacts:

  Installer:  src-tauri\target\release\bundle\nsis\IDR_0.1.0_x64-setup.exe
  Portable:   src-tauri\target\release\idr.exe

How a judge laptop runs the demo
--------------------------------
1. Copy the NSIS installer (or idr.exe) onto the laptop. USB stick is fine.
2. Install / double-click. Windows 10/11 already ship WebView2.
3. The window opens titled "IDR · SIH 26168 · Intelligent Dead Reckoning"
   (minimum 1280x800). Press "Run judge demo" in the console.
4. No internet required. Do not rely on venue wifi.

Identifier: in.sih26168.idr
Icons in src-tauri/icons/ are placeholders.
