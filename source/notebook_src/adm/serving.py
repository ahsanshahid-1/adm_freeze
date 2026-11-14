"""Model serving: isolated vLLM environment, model download/lock, server launch and preflight.

Platform profiles: Kaggle (2 x Tesla T4, 4-bit AWQ in float16) and the UA Little Rock CRC JupyterHub server
(1 x RTX PRO 6000 Blackwell 96 GB, the protocol's BF16 weights). Nothing here is used in local (mock) mode
except command planning, which is unit-tested."""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .core import now_iso, read_json, sha256_file, write_json

BACKBONES = {
    "A": {"base": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
          "candidates": ["cyankiwi/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit",
                         "QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ",
                         "stelterlab/Qwen3-Coder-30B-A3B-Instruct-AWQ"]},
    "B": {"base": "Qwen/Qwen2.5-Coder-14B-Instruct",
          "candidates": ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"]},
}
# main-plan-v2.md Section 9.1: two vendors, both dense ~30B, BF16, Apache 2.0. Both checkpoints are vision-language
# models; only text is used, so the vision encoder is not loaded (--language-model-only).
CRC_BACKBONES = {"A": "Qwen/Qwen3.8-27B", "B": "google/gemma-4-31B-it"}
VLLM_LADDER = [None, "0.10.1.1"]  # None = latest release at first install; the lock pins it afterwards
LAUNCH_VARIANTS = [
    {"name": "default", "args": [], "env": {}},
    {"name": "eager", "args": ["--enforce-eager"], "env": {}},
    {"name": "eager_no_p2p", "args": ["--enforce-eager"], "env": {"NCCL_P2P_DISABLE": "1", "NCCL_IB_DISABLE": "1"}},
]
PROFILES = {
    "kaggle": {"label": "2 x Tesla T4 (16 GB)", "gpus": 2, "tp": 2, "dtype": "float16", "port": 8000,
               "free_failed_weights": True,  # 20 GB-class disk: drop a failed candidate before the next one
               "vllm_ladder": VLLM_LADDER, "env": {}, "args": [],
               "base": {b: v["base"] for b, v in BACKBONES.items()},
               "candidates": {b: v["candidates"] for b, v in BACKBONES.items()}},
    # Section 9.1: BF16 weights of the named backbones; one at a time on a single 96 GB GPU.
    # Port 8000/8001 belong to the JupyterHub proxy on this server; weights are kept (2.7 TB disk, slow re-download).
    # The server has the CUDA driver but no CUDA toolkit (nvcc), so FlashInfer's JIT-compiled top-k/top-p sampler
    # cannot build; vLLM's PyTorch sampler is used instead. vLLM 0.10.x is not a usable fallback here (it fails with
    # transformers 5.x), so only the current release is tried and the lock pins it.
    "crc": {"label": "1 x NVIDIA RTX PRO 6000 Blackwell (96 GB)", "gpus": 1, "tp": 1, "dtype": "bfloat16", "port": 18000,
            "free_failed_weights": False, "vllm_ladder": [None], "env": {"VLLM_USE_FLASHINFER_SAMPLER": "0"},
            "args": ["--language-model-only"],
            "base": dict(CRC_BACKBONES),
            "candidates": {b: [repo] for b, repo in CRC_BACKBONES.items()}},
}
PORT = int(os.environ.get("ADM_VLLM_PORT", "0")) or None  # explicit override; otherwise the profile's port
LOCK_FILE = "models.lock.json"


def find_uv() -> list:
    """Use an existing uv binary if there is one; otherwise pip-install uv (with --user if the kernel env is read-only)."""
    import sysconfig
    for c in (os.environ.get("ADM_UV"), shutil.which("uv")):
        if c and Path(c).exists():
            return [c]
    user = not os.access(sysconfig.get_paths()["purelib"], os.W_OK)
    r = sh([sys.executable, "-m", "pip", "install", "-q", *(["--user"] if user else []), "uv"], 900)
    if r.returncode != 0:
        raise RuntimeError("could not install uv: " + r.stderr[-1500:])
    return [sys.executable, "-m", "uv"]


def sh(cmd, timeout=3600, env=None, log=None) -> subprocess.CompletedProcess:
    if log:
        log(f"$ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, **(env or {})})


def gpu_info() -> dict:
    try:
        q = sh(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader"], 60)
        rows = [r.split(", ") for r in q.stdout.strip().splitlines() if r.strip()]
        head = sh(["nvidia-smi"], 60).stdout
        cuda = None
        for tok in head.split("|"):
            if "CUDA Version" in tok:
                cuda = tok.split("CUDA Version:")[1].strip().split()[0]
        return {"gpus": [{"name": r[0], "memory": r[1], "driver": r[2], "compute_capability": r[3] if len(r) > 3 else None}
                         for r in rows], "cuda_driver_api": cuda}
    except Exception as e:
        return {"gpus": [], "error": str(e)}


def host_info() -> dict:
    import platform
    du = shutil.disk_usage("/")
    try:
        mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30
    except (ValueError, OSError, AttributeError):
        mem = None
    return {"python": sys.version.split()[0], "platform": platform.platform(), "cpus": os.cpu_count(),
            "ram_gib": round(mem, 1) if mem else None, "disk_free_gib": round(du.free / 2**30, 1)}


class Server:
    def __init__(self, env_dir: Path, models_dir: Path, configs_dir: Path, logs_dir: Path, log=print,
                 platform: str = "kaggle"):
        self.platform = platform
        self.profile = PROFILES[platform]
        self.env = Path(env_dir)
        self.models = Path(models_dir)
        self.configs = Path(configs_dir)
        self.logs = Path(logs_dir)
        self.logs.mkdir(parents=True, exist_ok=True)
        self.log = log
        self.proc = None
        self.started = None
        self.backbone = None
        self.gpu_seconds = {}
        self.port = PORT or self.profile["port"]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def python(self) -> Path:
        return self.env / "bin" / "python"

    @property
    def vllm_bin(self) -> Path:
        return self.env / "bin" / "vllm"

    def lock(self) -> dict:
        p = self.configs / LOCK_FILE
        return read_json(p) if p.exists() else {}

    def save_lock(self, lock: dict):
        write_json(self.configs / LOCK_FILE, lock)

    # ---------------------------------------------------------------- environment
    def installed_version(self) -> str | None:
        if not self.python.exists():
            return None
        r = sh([str(self.python), "-c", "import vllm,sys;sys.stdout.write(vllm.__version__)"], 300)
        return r.stdout.strip() if r.returncode == 0 else None

    def install(self, version: str | None) -> str:
        """Create an isolated environment so the kernel's own Python/PyTorch stack is untouched."""
        cur = self.installed_version()
        if cur and (version is None or cur == version):
            return cur
        if self.env.exists():
            shutil.rmtree(self.env)
        uv = find_uv()
        r = sh(uv + ["venv", str(self.env), "--python", "3.12", "--seed"], 900, log=self.log)
        if r.returncode != 0:
            raise RuntimeError("uv venv failed: " + r.stderr[-1500:])
        spec = f"vllm=={version}" if version else "vllm"
        r = sh(uv + ["pip", "install", "--python", str(self.python), spec, "--torch-backend=auto", "huggingface_hub"],
               3600, log=self.log)
        if r.returncode != 0:
            raise RuntimeError(f"vLLM install ({spec}) failed: " + r.stderr[-2500:])
        v = self.installed_version()
        if not v:
            raise RuntimeError("vLLM installed but cannot be imported")
        freeze = sh(uv + ["pip", "freeze", "--python", str(self.python)], 300).stdout
        (self.configs / "vllm_env.lock.txt").write_text(freeze)
        return v

    # ---------------------------------------------------------------- models
    def download(self, repo: str, revision: str | None) -> dict:
        target = self.models / repo.replace("/", "__")
        code = (
            "import json,sys\nfrom huggingface_hub import snapshot_download, HfApi\n"
            f"repo={repo!r}; rev={revision!r}\n"
            "info=HfApi().model_info(repo, revision=rev)\n"
            f"p=snapshot_download(repo, revision=info.sha, local_dir={str(target)!r}, max_workers=8)\n"
            "print(json.dumps({'sha': info.sha, 'path': p}))\n")
        free = shutil.disk_usage(self.models if self.models.exists() else "/").free / 2**30
        if free < 25:
            self.log(f"warning: only {free:.1f} GiB free for model weights")
        r = sh([str(self.python), "-c", code], 7200, env={"HF_HUB_ENABLE_HF_TRANSFER": "0"}, log=self.log)
        if r.returncode != 0:
            raise RuntimeError(f"download of {repo} failed: " + r.stderr[-2000:])
        info = json.loads(r.stdout.strip().splitlines()[-1])
        files = {}
        for fn in ["config.json", "tokenizer.json", "tokenizer_config.json", "generation_config.json",
                   "quantization_config.json", "chat_template.jinja"]:
            if (target / fn).exists():
                files[fn] = sha256_file(target / fn)
        weights = sorted(p.name for p in target.glob("*.safetensors"))
        wh = hashlib.sha256()
        for w in weights:  # weight files: hash of (name, size) plus the hub's commit sha pins content
            wh.update(f"{w}:{(target / w).stat().st_size}".encode())
        cfg = read_json(target / "config.json") if (target / "config.json").exists() else {}
        return {"repo": repo, "revision": info["sha"], "path": str(target), "file_hashes": files,
                "tokenizer_hash": files.get("tokenizer.json"), "weight_files": weights,
                "weight_manifest_hash": wh.hexdigest(),
                "quantization": cfg.get("quantization_config", {}).get("quant_method"),
                "downloaded": now_iso()}

    # ---------------------------------------------------------------- launch
    def command(self, model_path: str, served: str, variant: dict, tp: int | None = None, max_len: int = 16384,
                max_seqs: int = 16, util: float = 0.90) -> list:
        tp = tp or self.profile["tp"]
        return [str(self.vllm_bin), "serve", model_path, "--served-model-name", served,
                "--tensor-parallel-size", str(tp), "--dtype", self.profile["dtype"], "--max-model-len", str(max_len),
                "--gpu-memory-utilization", str(util), "--max-num-seqs", str(max_seqs), "--enable-prefix-caching",
                "--host", "127.0.0.1", "--port", str(self.port), "--seed", "0"] + self.profile["args"] + variant["args"]

    def launch_env(self, variant: dict) -> dict:
        return {"VLLM_WORKER_MULTIPROC_METHOD": "spawn", **self.profile["env"], **variant["env"]}

    def variants(self) -> list:
        # NCCL peer-to-peer settings only matter with more than one GPU
        return [v for v in LAUNCH_VARIANTS if self.profile["gpus"] > 1 or not v["env"]]

    def port_in_use(self) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            return s.connect_ex(("127.0.0.1", self.port)) == 0

    def start(self, model_path: str, served: str, variant: dict, timeout: float = 1800, **kw) -> bool:
        self.stop()
        if self.port_in_use():
            # never talk to (or report readiness of) a process this pipeline did not start
            raise RuntimeError(f"port {self.port} is already in use by another process; set ADM_VLLM_PORT to a free port")
        cmd = self.command(model_path, served, variant, **kw)
        logf = self.logs / f"vllm_{served}_{variant['name']}_{int(time.time())}.log"
        env = {**os.environ, **self.launch_env(variant)}
        for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            env.pop(v, None)
        self.log("$ " + " ".join(cmd))
        self.proc = subprocess.Popen(cmd, stdout=open(logf, "w"), stderr=subprocess.STDOUT, env=env,
                                     start_new_session=True)
        self.logfile = logf
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                self.log(f"server exited with code {self.proc.returncode}; log tail:\n" + self.tail())
                self.proc = None
                return False
            try:
                with urllib.request.urlopen(f"{self.url}/v1/models", timeout=5) as r:
                    if r.status == 200:
                        self.started = time.time()
                        self.backbone = served
                        self.log(f"server ready after {time.time() - t0:.0f}s")
                        return True
            except Exception:
                pass
            time.sleep(10)
        self.log("server did not become ready in time; log tail:\n" + self.tail())
        self.stop()
        return False

    def tail(self, n: int = 60) -> str:
        try:
            return "\n".join(Path(self.logfile).read_text(errors="replace").splitlines()[-n:])
        except Exception:
            return ""

    def stop(self):
        if self.proc is not None:
            if self.started:
                self.gpu_seconds[self.backbone] = (self.gpu_seconds.get(self.backbone, 0.0)
                                                   + self.profile["gpus"] * (time.time() - self.started))
            pgid = None
            try:
                pgid = os.getpgid(self.proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                self.proc.wait(60)
            except Exception:
                pass
            if pgid is not None:
                try:
                    os.killpg(pgid, signal.SIGKILL)  # engine-core children can outlive the API server process
                except Exception:
                    pass
            self.proc = None
            self.started = None
            self.backbone = None  # a second stop() (e.g. from a finally block) must not be accounted again
            self.wait_gpu_free()

    def wait_gpu_free(self, util: float = 0.90, timeout: float = 300):
        """Block until every GPU has enough free memory for the next server (vLLM releases memory asynchronously)."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                q = sh(["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"], 60)
                rows = [[float(x) for x in r.split(",")] for r in q.stdout.strip().splitlines() if r.strip()]
            except Exception:
                rows = []
            if not rows or all(free >= util * total for free, total in rows):
                return
            time.sleep(5)
        self.log(f"warning: GPU memory not released after {timeout:.0f}s")

    # ---------------------------------------------------------------- preflight
    def preflight(self, served: str, generation: dict) -> dict:
        from .llm import LLMError, VLLMClient, action_schema
        from .agents import parse_action
        res = {"served": served, "time": now_iso()}
        mode = None
        msgs = [{"role": "system", "content": "Reply with one JSON object."},
                {"role": "user", "content": 'Choose the action list_sources with empty args. Put the sum 17+25 in the thought.'}]
        for m in ("response_format", "structured_outputs", "guided_json"):
            c = VLLMClient(self.url, served, generation, m, timeout=300)
            try:
                out = c.complete(msgs, "single", 1)
                act, err = parse_action(out["text"], "single")
                if act is not None:
                    mode = m
                    res["schema_test"] = {"mode": m, "text": out["text"][:300], "action": act["action"],
                                          "contains_42": "42" in out["text"], "seconds": round(out["seconds"], 2)}
                    break
                res.setdefault("schema_errors", []).append(f"{m}: {err}: {out['text'][:200]}")
            except LLMError as e:
                res.setdefault("schema_errors", []).append(f"{m}: {str(e)[:300]}")
        res["structured_mode"] = mode
        if mode is None:
            res["ok"] = False
            return res
        # the constrained 'args' object must still carry free-form content
        c = VLLMClient(self.url, served, generation, mode, timeout=300)
        out = c.complete([{"role": "system", "content": "Reply with one JSON object."},
                          {"role": "user", "content": 'Call inspect_schema with args {"table": "observations"}.'}], "single", 2)
        act, _ = parse_action(out["text"], "single")
        res["args_test"] = {"text": out["text"][:300], "passed": bool(act and act["action"] == "inspect_schema"
                                                                        and act["args"].get("table") == "observations")}
        if not res["args_test"]["passed"]:
            res["ok"] = False
            return res
        # throughput: 8 concurrent agent-sized prompts
        filler = ("Catalog table observations has columns observation_id, sensor_1, sensor_2, sensor_3. " * 60)
        prompt = [{"role": "system", "content": "Reply with one JSON object."},
                  {"role": "user", "content": filler + "\nChoose list_sources."}]
        c = VLLMClient(self.url, served, generation, mode, timeout=600)
        t0 = time.time()
        with cf.ThreadPoolExecutor(8) as ex:
            outs = list(ex.map(lambda k: c.complete(prompt, "single", 100 + k), range(8)))
        dt = time.time() - t0
        res["throughput"] = {"concurrent_requests": 8, "wall_seconds": round(dt, 2),
                             "prompt_tokens_each": outs[0]["input_tokens"],
                             "output_tokens_total": sum(o["output_tokens"] for o in outs),
                             "output_tokens_per_second": round(sum(o["output_tokens"] for o in outs) / dt, 2),
                             "valid_json": sum(parse_action(o["text"], "single")[0] is not None for o in outs)}
        res["ok"] = res["throughput"]["valid_json"] >= 6 and res["schema_test"]["action"] == "list_sources"
        return res

    # ---------------------------------------------------------------- ladder
    def ensure(self, backbone: str, generation: dict, frozen: bool = False, max_minutes: float = 150) -> dict:
        """Bring up a backbone. Uses the lock if present; otherwise walks the fixed fallback order and
        records the first configuration that passes preflight. A frozen protocol never falls back."""
        lock = self.lock()
        t0 = time.time()
        entry = lock.get("backbones", {}).get(backbone)
        if entry:
            ladder = [(lock["vllm_version"], entry["repo"], entry["revision"], v) for v in LAUNCH_VARIANTS
                      if v["name"] == entry["launch_variant"]]
        elif frozen:
            raise RuntimeError(f"backbone {backbone} is not in the frozen model lock")
        else:
            versions = [lock["vllm_version"]] if lock.get("vllm_version") else self.profile["vllm_ladder"]
            ladder = [(ver, repo, None, var) for ver in versions for repo in self.profile["candidates"][backbone]
                      for var in self.variants()]
        failures = []
        for ver, repo, rev, var in ladder:
            if (time.time() - t0) / 60 > max_minutes:
                break
            try:
                installed = self.install(ver)
                m = self.download(repo, rev)
                if rev and m["revision"] != rev:
                    raise RuntimeError(f"revision mismatch {m['revision']} != {rev}")
                if not self.start(m["path"], backbone, var):
                    raise RuntimeError(f"server failed to start ({var['name']})")
                pf = self.preflight(backbone, generation)
                write_json(self.logs / f"preflight_{backbone}_{int(time.time())}.json", pf)
                if not pf.get("ok"):
                    raise RuntimeError(f"preflight failed: {json.dumps(pf)[:1500]}")
                lock = self.lock()
                if lock.get("vllm_version") and lock["vllm_version"] != installed and frozen:
                    raise RuntimeError("frozen vLLM version differs from installed version")
                lock["vllm_version"] = installed
                lock.setdefault("backbones", {})[backbone] = {**m, "base_model": self.profile["base"][backbone],
                                                              "launch_variant": var["name"],
                                                              "launch_command": self.command(m["path"], backbone, var),
                                                              "launch_env": self.launch_env(var),
                                                              "structured_mode": pf["structured_mode"],
                                                              "dtype": self.profile["dtype"], "preflight": pf}
                lock["platform"] = {"name": self.platform, "label": self.profile["label"]}
                lock["gpu"] = gpu_info()
                lock["host"] = host_info()
                self.save_lock(lock)
                return lock["backbones"][backbone]
            except Exception as e:
                failures.append({"vllm": ver, "repo": repo, "variant": var["name"], "error": str(e)[:1500]})
                self.log(f"[serving] attempt failed: {failures[-1]}")
                self.stop()
                # free disk from a failed candidate before trying the next repository
                tgt = self.models / repo.replace("/", "__")
                if (self.profile["free_failed_weights"] and not entry and var is self.variants()[-1]
                        and tgt.exists()):
                    shutil.rmtree(tgt, ignore_errors=True)
        write_json(self.logs / f"serving_failures_{backbone}.json", failures)
        raise RuntimeError(f"no working serving configuration for backbone {backbone}. "
                           f"See {self.logs}/serving_failures_{backbone}.json. The protocol forbids silently switching "
                           "to another model; revise and re-freeze the protocol instead.")
