# Cutflow

Cutflow is a v1 scaffold for an AI editor assistant for DaVinci Resolve users.
It gives editors a chat panel that sends constrained edit commands to a local
Python bridge, which then calls Resolve's scripting API when Resolve is
available.

The goal of v1 is to prove the integration loop:

```text
Editor prompt -> structured command -> local bridge -> DaVinci Resolve action
```

## What this v1 can do

- Show a chat-style assistant panel in `plugin/index.html`
- Run a local bridge at `http://127.0.0.1:8765`
- Parse basic prompts into safe actions:
  - "put caption \"New chapter\" here"
  - "add a smooth 20% zoom in to this clip"
  - "analyze audio and find b-roll of a busy city at night"
- Connect to DaVinci Resolve through Python scripting when available
- Fall back to dry-run mode for development without Resolve
- Search Pexels for licensed b-roll/images when `PEXELS_API_KEY` is set
- Add Resolve markers for caption and b-roll planning workflows when direct
  timeline insertion is not available

## Repository layout

```text
bridge/
  server.py          Local HTTP API used by the chat panel
  intents.py         Prompt-to-action parser for v1
  resolve_client.py  Resolve scripting API wrapper
  stock.py           Optional Pexels stock search

plugin/
  index.html         Chat panel UI
  app.js             Bridge client
  styles.css         Panel styles
  manifest.json      Metadata for packaging as a Resolve workflow integration

resolve_scripts/
  probe_resolve.py   Checks whether Resolve scripting is reachable
  send_chat.py       Sends a command to the bridge from the command line
```

## Run it locally without Resolve

Start the bridge in dry-run mode:

```bash
python bridge/server.py --dry-run
```

Open the panel:

```bash
python -m http.server 9000 -d plugin
```

Then visit:

```text
http://127.0.0.1:9000
```

Try:

```text
Add a smooth 20% zoom in to this clip
```

The UI will show the parsed command and dry-run result.

## Run it with DaVinci Resolve

1. Install DaVinci Resolve Studio or Resolve.
2. Enable external scripting in Resolve if your installation requires it.
3. Open a project and timeline.
4. Start the bridge:

   ```bash
   python bridge/server.py
   ```

5. Check the connection:

   ```bash
   python resolve_scripts/probe_resolve.py
   ```

6. Open `plugin/index.html` through a local web server or package it into a
   Resolve workflow integration panel.

The bridge searches the standard Resolve scripting module locations for macOS,
Windows, and Linux. If your Resolve install uses a custom path, add that path to
`PYTHONPATH` before starting the bridge.

## Stock media search

Set a Pexels API key to get licensed stock suggestions:

```bash
export PEXELS_API_KEY="your-api-key"
python bridge/server.py
```

Without the key, v1 returns a placeholder suggestion so the rest of the flow can
be tested.

## How Resolve integration works

The UI never edits Resolve directly. It sends JSON to the local bridge:

```json
{
  "message": "Add a smooth 20% zoom in to this clip"
}
```

The bridge parses that into a constrained action:

```json
{
  "action": "apply_zoom",
  "args": {
    "target": "current_clip",
    "end_zoom": 1.2,
    "style": "smooth_push_in"
  }
}
```

Then `bridge/resolve_client.py` calls Resolve's Python scripting API. If Resolve
is not available, the same action returns a dry-run response.

## Current limitations

This is intentionally a v1 scaffold, not a finished commercial plugin.

- Caption insertion uses Text+/title insertion when available, otherwise it adds
  a Resolve marker describing the caption.
- Zooms currently set clip zoom properties when the current timeline item is
  reachable. Smooth keyframed zooms require a deeper Resolve/Fusion keyframe
  implementation.
- "Analyze audio" currently means "plan b-roll for this prompt and add timeline
  markers." Real transcript-based audio analysis should be added with Whisper,
  Resolve timeline audio extraction, or a speech-to-text provider.
- Stock search supports Pexels first. Paid stock providers can be added behind
  the same `StockSearch` interface.
- `plugin/manifest.json` is metadata for packaging. Exact installation paths and
  manifest requirements vary by Resolve version and operating system.

## Next build steps

1. Replace `bridge/intents.py` with LLM tool calling while preserving the same
   action schema.
2. Add confirmation controls before destructive actions.
3. Implement true Text+ template insertion with style presets.
4. Add Fusion-based keyframed zoom templates.
5. Add media download/import/append after user approval.
6. Package the panel into Resolve's Workflow Integrations folder for each OS.
