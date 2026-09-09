# Web surfaces

## Phone-tracker dashboard (demo)

From the **repo root**:

```text
python -m web.tracker_server
```

Open `http://127.0.0.1:8787/` on the laptop. Enter this machine's **LAN IPv4**
in the tracker-flavor app Settings (not `127.0.0.1` — that is the phone).

**Find the laptop IP (Windows):** run `ipconfig` and copy **IPv4 Address** under
the active Wi-Fi or Ethernet adapter (e.g. `192.168.1.42`). Phone and laptop
must share a LAN (or one hotspots the other).

Endpoints: `POST /ingest`, `GET /feed`, `GET /`. Stdlib only; binds `0.0.0.0:8787`.
