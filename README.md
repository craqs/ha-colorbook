# 🎨 Kolorowanki — Home Assistant Add-on

> AI-generated coloring book pages for children, printed on your network printer.

[![Add to Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fcraqs%2Fha-colorbook)

---

## What it does

Open the panel on your phone, type a topic like **"lis biegnący przez las"**,
and in seconds you have a clean black-and-white coloring page ready to print
on your Brother (or any AirPrint-capable) network printer.

**Features**

- 🖼 AI-generated line-art via **OpenAI `gpt-image-1`** — thick outlines, white
  background, sized for little hands
- 🖨 Prints directly to a network printer (IPP / AirPrint) — auto-discovers
  the right queue, no CUPS config needed
- 🎲 **Random topic** button (Polish, child-friendly)
- ✅ **Auto-print** toggle — type topic → done, page comes out of the printer
- ✏️ **Refine** the image with follow-up prompts, or regenerate from scratch
- 🗂 **Gallery** of all generated pages with reprint & delete
- 📱 Mobile-friendly (iPhone-optimised), dark mode, works via HA Ingress

---

## Installation

### One-click (recommended)

Click the button above — it opens the **Add repository** dialog in your
Home Assistant instance with the URL pre-filled.

### Manual

1. In Home Assistant go to **Settings → Add-ons → Add-on Store**
2. Click **⋮ → Repositories**
3. Paste `https://github.com/craqs/ha-colorbook` and click **Add**
4. Find **Kolorowanki** in the store and click **Install**

---

## Configuration

| Option | Default | Description |
|---|---|---|
| `openai_api_key` | *(env OPENAI_TOKEN)* | OpenAI API key — leave blank if already set as an env var |
| `printer_host` | *(required)* | Hostname or IP of the printer / AirPrint server (e.g. `BRN001122.local`) |
| `printer_port` | `631` | IPP port |
| `printer_queue` | *(auto-discover)* | IPP queue path (e.g. `printers/Brother`). Leave blank to auto-detect from CUPS |
| `paper_size` | `A4` | `A4` or `Letter` |
| `image_size` | `1024x1536` | Resolution passed to `gpt-image-1` |
| `image_quality` | `medium` | `low` / `medium` / `high` / `auto` |
| `auto_accept_default` | `false` | Pre-tick the "Drukuj automatycznie" toggle on load |
| `openai_image_model` | `gpt-image-1` | Image generation model |
| `openai_chat_model` | `gpt-4o-mini` | Chat model used for random topic generation |

---

## Local development

```bash
cd colorbook
export OPENAI_API_KEY=sk-...
export PRINTER_HOST=192.168.1.42
export DATA_DIR=./devdata
mkdir -p devdata/images
pip install -r requirements.txt
flask --app app.main run --debug -p 8099
```

Printer queue discovery (if unsure what to set):

```bash
python -m app.printer --discover
```

---

## Architecture

```
colorbook/          HA add-on directory
├── config.yaml     Add-on manifest (ingress, options schema)
├── Dockerfile      Alpine + Python 3.12, no system CUPS needed
├── run.sh          Reads /data/options.json → env → gunicorn
└── app/
    ├── main.py         Flask routes + IngressPrefixMiddleware
    ├── openai_client.py  gpt-image-1 + gpt-4o-mini random topics
    ├── printer.py      Hand-rolled IPP client with auto-discovery
    ├── pdf.py          PNG → A4 PDF via Pillow @300 DPI
    └── history.py      SQLite + /data/images/ PNG store
```

---

## License

MIT
