#!/usr/bin/env python3

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
VALUES_FILE = ROOT / "values.yaml"
OUTPUT_DIR = ROOT / "kubeconfigs"


def run(*args):
    result = subprocess.run(
        args,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\n{result.stderr.strip()}"
        )

    return result.stdout.strip()


def load_users():
    with VALUES_FILE.open(encoding="utf-8") as file:
        values = yaml.safe_load(file)

    users = []

    mentor = values["mentor"]
    users.append({
        "name": mentor["name"],
        "namespace": mentor["namespace"],
    })

    for student in values.get("students", []):
        users.append({
            "name": student["name"],
            "namespace": student.get("namespace", student["name"]),
        })

    identities = [(user["namespace"], user["name"]) for user in users]

    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate ServiceAccount identities in values.yaml")

    return users


def get_cluster_config():
    config = json.loads(
        run(
            "kubectl",
            "config",
            "view",
            "--raw",
            "--minify",
            "-o",
            "json",
        )
    )

    context_name = config["current-context"]
    context = next(
        item["context"]
        for item in config["contexts"]
        if item["name"] == context_name
    )

    cluster = next(
        item["cluster"]
        for item in config["clusters"]
        if item["name"] == context["cluster"]
    )

    server = cluster["server"]

    if cluster.get("insecure-skip-tls-verify"):
        raise RuntimeError(
            "Admin kubeconfig uses insecure-skip-tls-verify. "
            "Configure a trusted cluster CA first."
        )

    ca_data = cluster.get("certificate-authority-data")

    if not ca_data:
        ca_path = cluster.get("certificate-authority")

        if not ca_path:
            raise RuntimeError("Cluster CA is missing from admin kubeconfig")

        ca_data = base64.b64encode(
            Path(ca_path).expanduser().read_bytes()
        ).decode()

    return server, ca_data


def create_kubeconfig(name, namespace, server, ca_data, duration):
    run(
        "kubectl",
        "get",
        "serviceaccount",
        name,
        "-n",
        namespace,
        "-o",
        "name",
    )

    token = run(
        "kubectl",
        "create",
        "token",
        name,
        "-n",
        namespace,
        f"--duration={duration}",
    )

    config = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [
            {
                "name": "learning-lab",
                "cluster": {
                    "server": server,
                    "certificate-authority-data": ca_data,
                },
            }
        ],
        "users": [
            {
                "name": name,
                "user": {
                    "token": token,
                },
            }
        ],
        "contexts": [
            {
                "name": name,
                "context": {
                    "cluster": "learning-lab",
                    "user": name,
                    "namespace": namespace,
                },
            }
        ],
        "current-context": name,
    }

    target = OUTPUT_DIR / f"{name}.kubeconfig"

    fd, temporary = tempfile.mkstemp(
        prefix=f".{name}.",
        dir=OUTPUT_DIR,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            yaml.safe_dump(config, file, sort_keys=False)

        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--duration",
        default="24h",
        help="Requested ServiceAccount token lifetime (default: 24h)",
    )
    args = parser.parse_args()

    users = load_users()

    OUTPUT_DIR.mkdir(mode=0o700, exist_ok=True)
    os.chmod(OUTPUT_DIR, 0o700)

    server, ca_data = get_cluster_config()

    print(f"Cluster: {server}")
    print(f"Users: {len(users)}")
    print()

    failed = []

    for user in users:
        name = user["name"]
        namespace = user["namespace"]

        try:
            target = create_kubeconfig(
                name,
                namespace,
                server,
                ca_data,
                args.duration,
            )

            print(f"[OK] {namespace}/{name} -> {target.name}")

        except Exception as error:
            failed.append(name)
            print(f"[ERROR] {name}: {error}", file=sys.stderr)

    print()
    print(f"Generated: {len(users) - len(failed)}/{len(users)}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
