# Fortograph plugin for Hermes

Redact and restore images through a remote [Fortograph](https://fortograph.selectiveencryption.com) selective-encryption API.

The plugin is pure Python standard library: no `pip` dependencies.

## Tools

| Tool | Purpose |
|---|---|
| `fortograph_status` | Check that the configured Fortograph API is reachable |
| `fortograph_redact` | Redact one or more regions and save the processed image |
| `fortograph_unredact` | Restore a previously redacted image using the same password |

Redaction modes: `fortographthumbnail` (default), `fortograph`, `fortographregiononly`.
Unredaction modes: `unfortographthumbnail` (default), `unfortograph`, `unfortographregiononly`.

## Install on another computer

1. Copy this `fortograph/` directory into the target machine's Hermes plugins
   directory:

   ```bash
   mkdir -p ~/.hermes/plugins
   cp -r fortograph ~/.hermes/plugins/fortograph
   ```

   Or, if you have a zip:

   ```bash
   unzip fortograph-hermes-plugin.zip -d ~/.hermes/plugins/
   ```

2. Enable it:

   ```bash
   hermes plugins enable fortograph
   ```

3. Set the default password once (or pass `password` on every call). Use
   Hermes's own secret flow — **Settings → Plugins → Fortograph → "Default
   redaction password"** in the Desktop app, or the same masked field in the TUI.
   Hermes stores it through its credential route as `FORTOGRAPH_PASSWORD` in
   `.env`; the plugin reads it with `agent.secret_scope.get_secret`. Do not
   hand-edit `.env` and do not export the password into the process environment.

4. Verify:

   ```bash
   hermes -z 'Call fortograph_status and print the raw JSON' -t fortograph
   ```

If you publish this directory as a Git repository, install it with:

```bash
hermes plugins install <owner>/<repo> --enable
```

## Configuration

Settings live under `plugins.entries.fortograph.settings` and can also be set
through the Desktop plugin settings form.

| Key | Default | Notes |
|---|---|---|
| `base_url` | `https://fortograph.selectiveencryption.com` | Deployment root. The plugin auto-detects whether to call `/api/image` or `/Fortograph/api/image`. |
| `timeout` | `120` | Request timeout in seconds. |
| `output_dir` | — | Optional extra directory results may be written into, besides the input image's own directory. |
| `password` | — | `FORTOGRAPH_PASSWORD` secret, set through Hermes's credential route (Desktop settings form), never in `config.yaml`. |

Environment overrides:

- `FORTOGRAPH_BASE_URL` — overrides `base_url`.
- `FORTOGRAPH_PASSWORD` — resolved by `agent.secret_scope.get_secret` (which
  reads the active profile's `.env`); the plugin never reads it from a bare
  `os.environ` lookup.

Examples:

- Public host: `https://fortograph.selectiveencryption.com`
- Direct Jetty (same tailnet): `http://ubuntu:8081/Fortograph`
- Direct Jetty root (auto-detected): `http://ubuntu:8081`

## Usage

Interactive:

```bash
hermes
```

> Use fortograph_redact on /home/me/photo.jpg with password "secret" and a
> rectangle at x=10 y=20 width=100 height=50. Save it next to the original.

One-shot:

```bash
hermes -z 'Use fortograph_status and print the JSON' -t fortograph
```

Regions use pixel coordinates and support `rectangle`, `circle`, and `text`:

```json
[
  {"shape": "rectangle", "color": "#000000",
   "coordinates": {"x": 57, "y": 34, "width": 179, "height": 86}},
  {"shape": "circle", "color": "#000000",
   "coordinates": {"x": 120, "y": 90, "radius": 40}}
]
```

## Safety

- `image_path` must be a real image (JPEG, PNG, GIF, WEBP, BMP or TIFF, checked
  by magic bytes). Other files — an SSH key or `~/.hermes/.env`, for example —
  are refused before anything is uploaded.
- `output_path` may only point inside the input image's own directory or the
  configured `output_dir`. The plugin refuses symlinks, refuses to overwrite an
  existing non-image file, and refuses to write a server response that is not
  itself an image.
- The password is resolved only through Hermes's secret scope
  (`agent.secret_scope.get_secret`), never from a bare environment read.

## Notes

- The API accepts uploads up to 10 MB.
- Redaction requires a non-empty region list; unredaction needs the original password.
- A wrong password returns `Invalid password or corrupted payload`.
- Requests send a `Hermes-Fortograph/<version>` User-Agent because the public host
  blocks the default Python urllib signature.
- Long-running gateway sessions load plugin tools at session start; start a new
  session or reload plugins after installing or updating.
