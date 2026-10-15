"""Cloud Run Sandbox dispatcher -- Task 45 (docs/BACKLOG.md). The real, production counterpart
to Task 42/43's spike dispatchers (scripts/spike_cloudrun_sandbox, scripts/spike_cloudrun_airflow),
generalized to one flexible endpoint instead of the several special-purpose ones those
accumulated while spiking, and toolchain-baked for libphonenumber (Java 21 + Maven, per
docs/SETUP.md's already-confirmed local versions) instead of Airflow's Python stack.

Real design point, corrected 2026-09-27 after a real failure: the sandbox's tar travels via a GCS
object (a `gs://` URI in the request/response JSON), not inline as base64 in the HTTP body itself.
First version did exactly that -- fine for a small marker-file test, but real evidence (Cloud
Run's own log: "Response size was too large. Please consider reducing response size.", alongside
the sandboxed command itself succeeding with exit_code=0) showed even a single-commit, depth-1
checkout of libphonenumber's real working tree (binary phone-metadata/geocoding resource files,
not just source) is big enough to blow past Cloud Run's real, documented ~32MB request/response
body limit once base64-encoded. GCS has no such limit and is the standard fix for exactly this
class of problem -- large binary payload, small control-plane message.

Auth: this service is deployed *without* --allow-unauthenticated -- Cloud Run's own IAM front
door verifies the caller's OIDC identity token before a request ever reaches this process (the
same roles/run.invoker pattern already used elsewhere in this project, docs/DECISIONS.md). No
independent verification needed here, unlike webhook/main.py, which has to verify GitHub's HMAC
signature itself because GitHub isn't a GCP-authenticated caller. The bucket used for tar
exchange needs a lifecycle rule (age-based deletion) set at creation time -- this process doesn't
clean up its own uploaded objects, deliberately: simpler and robust against a crash between
upload and the caller's download, at the cost of some short-lived storage until the rule reaps it.

Run locally (no --sandbox-launcher, `sandbox` won't exist, and no real bucket -- for
syntax-checking only): uvicorn dispatcher.main:app --reload --port 8081
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
import uuid

from fastapi import FastAPI
from google.cloud import storage
from pydantic import BaseModel

logger = logging.getLogger("dispatcher")

app = FastAPI(title="triagent cloud run sandbox dispatcher")

DEFAULT_TIMEOUT_SECONDS = 300.0

# Required, not defaulted -- a dispatcher that silently no-ops tar exchange because the bucket
# wasn't configured would fail confusingly deep inside a sandbox call, not here at startup.
GCS_BUCKET = os.environ["TRIAGENT_SANDBOX_GCS_BUCKET"]
_storage_client = storage.Client()
_bucket = _storage_client.bucket(GCS_BUCKET)


class DoRequest(BaseModel):
    command: list[str]
    cwd: str = "/root/repo"
    write: bool = False
    allow_egress: bool = False
    env: dict[str, str] = {}
    export: bool = False
    import_tar_gcs: str | None = None  # a bare object name within GCS_BUCKET, not a full gs:// URI
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS


class DoResponse(BaseModel):
    stdout: str
    stderr: str
    returncode: int
    export_tar_gcs: str | None = None  # a bare object name within GCS_BUCKET


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/do", response_model=DoResponse)
async def do(req: DoRequest) -> DoResponse:
    """Restores req.import_tar_gcs (an object in GCS_BUCKET, if given) into a fresh sandbox, runs
    req.command there (in req.cwd -- wrapped in `sh -c 'cd ... && exec ...'` since `sandbox do`
    itself has no --cwd flag, per Task 42/43's own confirmed real invocation shape), optionally
    exports the resulting writable overlay back out to a fresh GCS object. Never raises on the
    sandboxed command's own failure or timeout -- both come back as a normal nonzero returncode,
    matching agents/sandbox/process.py's local run_subprocess contract, so a calling agent can
    react instead of the whole run crashing."""
    with tempfile.TemporaryDirectory(prefix="triagent-do-", dir="/tmp") as workdir:
        args = ["sandbox", "do"]
        if req.write:
            args.append("--write")
        if req.allow_egress:
            args.append("--allow-egress")
        for k, v in req.env.items():
            args += ["--env", f"{k}={v}"]

        import_tar_path = os.path.join(workdir, "import.tar")
        if req.import_tar_gcs:
            _bucket.blob(req.import_tar_gcs).download_to_filename(import_tar_path)
            args.append(f"--import-tar={import_tar_path}")

        export_tar_path = os.path.join(workdir, "export.tar")
        if req.export:
            args.append(f"--export-tar={export_tar_path}")

        wrapped = f"cd {shlex.quote(req.cwd)} && exec {shlex.join(req.command)}"
        args += ["--", "/bin/sh", "-c", wrapped]

        try:
            result = subprocess.run(
                args, capture_output=True, text=True, errors="replace", timeout=req.timeout_seconds
            )
        except subprocess.TimeoutExpired:
            return DoResponse(
                stdout="", stderr=f"command timed out after {req.timeout_seconds}s", returncode=-1
            )
        except OSError as e:
            return DoResponse(stdout="", stderr=f"could not invoke sandbox launcher: {e}", returncode=-1)

        export_tar_object = None
        if req.export and os.path.exists(export_tar_path):
            export_tar_object = f"exports/{uuid.uuid4().hex}.tar"
            _bucket.blob(export_tar_object).upload_from_filename(export_tar_path)

        return DoResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            export_tar_gcs=export_tar_object,
        )
