"""Checks that system.yaml matches the repository: paths exist and calls match OpenAPI.

The JSON schema only checks the shape of system.yaml; this script checks it against the code.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main():
    system = yaml.safe_load((ROOT / "system.yaml").read_text())
    errors = []
    if not (ROOT / system["ui"]["path"]).is_dir():
        errors.append(f"ui.path {system['ui']['path']} does not exist")
    for name, service in system["services"].items():
        for key in ("path", "openapi", "migrations"):
            if not (ROOT / service[key]).exists():
                errors.append(f"{name}.{key}: {service[key]} does not exist")
    for name in system["ui"]["calls"]:
        if name not in system["services"]:
            errors.append(f"ui calls unknown service {name}")
    for name, service in system["services"].items():
        for call in service.get("calls", []):
            target = system["services"].get(call["service"])
            if target is None:
                errors.append(f"{name} calls unknown service {call['service']}")
                continue
            if call["url_env"] not in service["env"]:
                errors.append(f"{name}: {call['url_env']} is not listed in env")
            paths = yaml.safe_load((ROOT / target["openapi"]).read_text())["paths"]
            for endpoint in call["endpoints"]:
                method, path = endpoint.split(" ", 1)
                if method.lower() not in paths.get(path, {}):
                    errors.append(f"{name} calls {endpoint}, not in {target['openapi']}")
    for error in errors:
        print("ERROR:", error)
    print("system.yaml matches the repository" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
