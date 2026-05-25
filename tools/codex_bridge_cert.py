#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a local self-signed TLS certificate for Codex Bridge.")
    parser.add_argument("--config", default=".codex-bridge/server.json", help="Bridge config to update.")
    parser.add_argument("--out-dir", default=".codex-bridge/tls", help="Directory for cert/key PEM files.")
    parser.add_argument("--host", action="append", default=[], help="DNS name or IP address to include. Repeatable.")
    parser.add_argument("--days", type=int, default=825, help="Certificate validity in days.")
    parser.add_argument("--no-config-update", action="store_true", help="Only write PEM files.")
    return parser


def subject_alt_names(values: list[str]) -> list[x509.GeneralName]:
    names: list[x509.GeneralName] = []
    for value in values:
        item = value.strip()
        if not item:
            continue
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(item)))
        except ValueError:
            names.append(x509.DNSName(item))
    return names


def default_hosts() -> list[str]:
    hosts = {"localhost", "127.0.0.1", socket.gethostname()}
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
            address = item[4][0]
            if address and not address.startswith("127."):
                hosts.add(address)
    except OSError:
        pass
    return sorted(hosts)


def write_config(config_path: Path, cert_file: Path, key_file: Path) -> None:
    data: dict[str, object] = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    server = data.setdefault("server", {})
    assert isinstance(server, dict)
    tls = server.setdefault("tls", {})
    assert isinstance(tls, dict)
    tls["enabled"] = True
    tls["cert_file"] = str(cert_file)
    tls["key_file"] = str(key_file)
    server["public_base_url"] = f"https://127.0.0.1:{server.get('port', 8765)}"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cert_file = out_dir / "codex-bridge-cert.pem"
    key_file = out_dir / "codex-bridge-key.pem"
    hosts = sorted(set(default_hosts() + args.host))

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Codex Bridge LAN"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local Codex Bridge"),
        ]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=max(1, args.days)))
        .add_extension(x509.SubjectAlternativeName(subject_alt_names(hosts)), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    if not args.no_config_update:
        write_config(config_path, cert_file, key_file)
    print(json.dumps({"cert_file": str(cert_file), "key_file": str(key_file), "hosts": hosts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
