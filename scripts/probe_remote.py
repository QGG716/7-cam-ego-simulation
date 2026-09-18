"""Read-only installed-environment inventory; does not import/start Isaac."""
import ast
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    return {"argv": args, "returncode": result.returncode,
            "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


packages = {}
for name in ("isaacsim", "isaacsim-sensor", "isaacsim-kernel", "isaacsim-replicator"):
    try:
        packages[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        packages[name] = None

site = Path(sys.prefix) / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages"
isaac = site / "isaacsim"
cameras = []
if isaac.is_dir():
    for path in isaac.rglob("camera.py"):
        if "sensors.camera" not in str(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        methods = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                part in node.name for part in ("opencv", "fisheye", "projection", "lens")
            ):
                methods.append({"name": node.name, "line": node.lineno,
                                "arguments": ast.unparse(node.args),
                                "doc": (ast.get_docstring(node) or "")[:700]})
        cameras.append({"path": str(path), "methods": methods})

result = {
    "platform": platform.platform(), "python": sys.version,
    "executable": sys.executable, "prefix": sys.prefix,
    "os_release": Path("/etc/os-release").read_text(),
    "gpu": command(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv"]),
    "packages": packages, "camera_source_inventory": cameras,
    "entrypoint": {"path": str(Path(sys.prefix) / "bin/isaacsim"),
                   "exists": (Path(sys.prefix) / "bin/isaacsim").is_file()},
    "runtime_launch": "NOT_RUN: baseline model package missing; inventory only",
}
print(json.dumps(result, ensure_ascii=False, indent=2))
