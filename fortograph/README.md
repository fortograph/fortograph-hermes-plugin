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

3. Set the default password once (or pass `password` on every call):

   ```bash
   echo 'FORTOGRAPH_PASSWORD=your-password' >> ~/.hermes/.env
   ```

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
| `password` | — | Stored as the `FORTOGRAPH_PASSWORD` secret in `.env`. |

Environment overrides:

- `FORTOGRAPH_BASE_URL` — overrides `base_url`.
- `FORTOGRAPH_PASSWORD` — overrides the default password.

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

## Notes

- The API accepts uploads up to 10 MB.
- Redaction requires a non-empty region list; unredaction needs the original password.
- A wrong password returns `Invalid password or corrupted payload`.
- Requests send a `Hermes-Fortograph/<version>` User-Agent because the public host
  blocks the default Python urllib signature.
- Long-running gateway sessions load plugin tools at session start; start a new
  session or reload plugins after installing or updating.
