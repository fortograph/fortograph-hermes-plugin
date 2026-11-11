# Fortograph plugin for Hermes

[Fortograph](https://fortograph.selectiveencryption.com) is selective-encryption
image redaction: redacted regions are not just painted over — they are encrypted
and embedded in the image, so **the original can be restored later with the
password**. This repo is a [Hermes Agent](https://hermes-agent.nousresearch.com)
plugin that exposes that as three agent tools.

```
photo.jpg  --fortograph_redact-->  redacted.jpg   (regions encrypted, not just covered)
redacted.jpg --fortograph_unredact-->  photo.jpg   (byte-identical round trip)
```

The plugin lives in [`fortograph/`](fortograph/) — see its
[README](fortograph/README.md) for tools, configuration and usage.

## What it gives Hermes

| Tool | Purpose |
|---|---|
| `fortograph_status` | Check that the configured Fortograph API is reachable |
| `fortograph_redact` | Redact regions of a local image (encrypted redaction) |
| `fortograph_unredact` | Restore a redacted image with the password |

Redaction modes: `fortographthumbnail` (default), `fortograph`, `fortographregiononly`;
unredaction modes: `unfortographthumbnail`, `unfortograph`, `unfortographregiononly`.

## Why a plugin (and not a skill or a prompt)

The plugin ships typed tool schemas Hermes can call autonomously, resolves
secrets through Hermes's secret scope (`FORTOGRAPH_PASSWORD`), is configurable
per-install (`base_url`, `timeout`) through the Desktop plugin settings form,
and validates against the Hermes plugin catalog admission gate. Pure Python
standard library — no `pip` dependencies.

## Install

```bash
hermes plugins install <owner>/<this-repo>
```

or from the catalog once listed:

```bash
hermes plugins install fortograph
```

## Test

```bash
python3 tests/e2e_roundtrip.py            # uses the bundled sample image
python3 tests/e2e_roundtrip.py --image /path/to/your.jpg
```

The round-trip test asserts the restored image is byte-identical (sha256) to
the original.

## License

MIT — see [LICENSE](LICENSE). The Fortograph server it talks to is a separate
project; the plugin only needs its public HTTP API.
