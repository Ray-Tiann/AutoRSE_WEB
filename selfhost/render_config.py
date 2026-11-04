#!/usr/bin/env python3
"""Render non-secret AutoRSE Caddy/systemd environment configuration."""
from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

from build_release import public_origin

HERE = Path(__file__).resolve().parent


def render(origin: str, output: Path) -> None:
    origin = public_origin(origin)
    host = urlsplit(origin).hostname
    try:
        ipaddress.ip_address(host)
        issuer = ("tls {\n        issuer acme {\n"
                  "            dir https://acme-v02.api.letsencrypt.org/directory\n"
                  "            profile shortlived\n        }\n    }")
    except ValueError:
        issuer = "tls {\n        issuer acme {\n            dir https://acme-v02.api.letsencrypt.org/directory\n        }\n    }"
    config = (HERE / "deploy/Caddyfile.template").read_text()
    config = config.replace("@SITE_ADDRESS@", host).replace("@TLS_ISSUER@", issuer)
    environment = (HERE / "deploy/selfhost.env.example").read_text()
    environment = environment.replace("https://114.66.48.196", origin)
    if output.exists():
        raise ValueError("Output exists; choose a new configuration directory")
    output.mkdir(parents=True, mode=0o700)
    for name, text in (("Caddyfile", config), ("selfhost.env", environment)):
        with (output / name).open("x") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(text)
    print(f"Rendered public-origin configuration: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    render(args.origin, args.output_dir)
