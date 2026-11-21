"""Opt-in loopback-only two-model room; not a model, avatar renderer, or identity provider."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
from typing import Callable
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from .asset_preview import preview_asset_bytes
from .model import Entity, Position3
from .rendering import render_scene_json
from .runtime import HabitatRuntime

MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}(?:/[A-Za-z0-9][A-Za-z0-9._-]{0,63})?(?::[A-Za-z0-9][A-Za-z0-9._-]{0,63})?$")
MAX_BODY = 20000
MAX_MESSAGE = 2000
MAX_CONTEXT = 10
# An exact allowlist: never map arbitrary user-supplied paths into the host filesystem.
SANDBOX_ASSETS = {
    "/sandbox": ("sandbox.html", "text/html; charset=utf-8"),
    "/sandbox/": ("sandbox.html", "text/html; charset=utf-8"),
    "/sandbox/sandbox.js": ("sandbox.js", "text/javascript; charset=utf-8"),
    "/sandbox/vendor/three.module.js": ("vendor/three.module.js", "text/javascript; charset=utf-8"),
    "/sandbox/vendor/three.core.js": ("vendor/three.core.js", "text/javascript; charset=utf-8"),
    "/sandbox/vendor/loaders/GLTFLoader.js": ("vendor/loaders/GLTFLoader.js", "text/javascript; charset=utf-8"),
    "/sandbox/vendor/utils/BufferGeometryUtils.js": ("vendor/utils/BufferGeometryUtils.js", "text/javascript; charset=utf-8"),
    "/sandbox/vendor/utils/SkeletonUtils.js": ("vendor/utils/SkeletonUtils.js", "text/javascript; charset=utf-8"),
    "/sandbox/vendor/LICENSE": ("vendor/LICENSE", "text/plain; charset=utf-8"),
}

HTML = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Habitat | local two-model room</title>
<style>
body{background:#101a27;color:#edf2f8;font:16px system-ui;margin:0 auto;max-width:900px;padding:20px}
header{border-bottom:1px solid #526071;padding-bottom:10px}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px}
section{border:1px solid #526071;border-radius:12px;padding:15px;min-height:100px}
.round{width:65px;height:65px;border-radius:50%;background:#628ca2;margin:10px auto}
section:nth-child(2) .round{background:#a48a69}
small{color:#bec9d6}#log{white-space:pre-wrap;border:1px solid #526071;border-radius:8px;
min-height:140px;max-height:320px;overflow:auto;padding:12px;margin:16px 0}
textarea{box-sizing:border-box;width:100%;padding:10px;background:#e9eef4;color:#152130}
button{margin:8px 4px 8px 0;padding:10px 14px;cursor:pointer}
button:disabled{opacity:.5}
@media(max-width:620px){main{grid-template-columns:1fr}}
</style>
<header><h1>Habitat: Two-model room</h1><p><small>Local experiment only.
Neither slot authenticates a person or Vera. Circles are NOT finished 3D models.
No saved transcript, automatic agent loop, remote access, or physical actions.</small></p><p><a href="/sandbox">Play in the 3D sandbox</a></p></header>
<main><section><div class="round" aria-hidden="true"></div><h2>Vera slot</h2>
<small>Unverified local model candidate</small></section>
<section><div class="round" aria-hidden="true"></div><h2>JACK slot</h2>
<small>Unverified native analytic JACK or generic local placeholder; neither is persona-qualified</small></section></main>
<div id="log" role="log" aria-live="polite"></div>
<label for="message">Message to selected local model</label>
<textarea id="message" rows="3" maxlength="2000"></textarea>
<div><button data-target="vera">Ask Vera slot</button>
<button data-target="jack">Ask JACK slot</button>
<button id="pass" disabled>Pass last reply to other slot</button>
<button id="clear">Clear browser transcript</button></div>
<small>Messages remain in this browser tab except when sent to localhost for inference.
Check your local model configuration before entering private information.</small>
<script>
"use strict";
const log=document.getElementById("log");
const entry=document.getElementById("message");
const pass=document.getElementById("pass");
let history=[],last=null,busy=false;
function add(speaker,text){
 const p=document.createElement("p");
 const strong=document.createElement("strong");
 strong.textContent=speaker+": ";
 p.append(strong,document.createTextNode(text));
 log.append(p);log.scrollTop=log.scrollHeight;
}
function disable(value){
 busy=value;
 document.querySelectorAll("button[data-target]").forEach(b=>b.disabled=value);
 pass.disabled=value||last===null;
}
async function ask(target,body,fromPass=false){
 if(busy||!body.trim())return;
 const context=history.slice(-10);
 disable(true);
 try{
  const r=await fetch("/api/turn",{method:"POST",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({target:target,message:body,context:context})});
  const data=await r.json();
  if(!r.ok)throw Error(data.error||"Request failed");
  if(!fromPass){add("Human",body);history.push({speaker:"human",text:body});}
  else{add("Forwarded "+last.speaker,body);}
  add(target.toUpperCase()+" (unverified)",data.reply);
  history.push({speaker:target,text:data.reply});
  history=history.slice(-10);
  last={speaker:target,text:data.reply};pass.disabled=false;
 }catch(err){add("Room error",String(err.message||err));}
 finally{disable(false);}
}
document.querySelectorAll("button[data-target]").forEach(b=>b.onclick=()=>{
 const body=entry.value.trim();if(body){entry.value="";ask(b.dataset.target,body);}
});
pass.onclick=()=>{
 if(!last||busy)return;
 const target=last.speaker==="vera"?"jack":"vera";
 const message="Other local model said: "+last.text.slice(0,1900);
 ask(target,message,true);
};
document.getElementById("clear").onclick=()=>{
 if(busy)return;history=[];last=null;log.replaceChildren();pass.disabled=true;
};
</script></html>"""

SYSTEM = {
    "vera": "You are an UNVERIFIED local model running in a Vera demo slot. "
            "Do not claim to be the canonical Vera, to remember prior chats, or to have authority. "
            "Respond conversationally and label uncertainty.",
    "jack": "You are a GENERIC LOCAL PLACEHOLDER running in the JACK demo slot. "
            "You are not a trained copy of a particular human and must not claim personal memories. "
            "Be candid, careful, and open to correction.",
}


def validate_model(value: str) -> str:
    if type(value) is not str or len(value) > 128 or not MODEL_NAME.fullmatch(value) or any(piece in (".", "..") for piece in value.split(":")[0].split("/")):
        raise ValueError("model name must be a local Ollama tag")
    return value


def make_scene() -> str:
    world = HabitatRuntime()
    for entity_id, x in (("vera", -1.0), ("jack", 1.0)):
        receipt = world.spawn(Entity(entity_id, "AVATAR", "two-model-room",
                                     Position3(x, 0, 0),
                                     {"binding": "UNVERIFIED_LOCAL_MODEL",
                                      "geometry": "NOT_BOUND"}))
        if not receipt.accepted:
            raise RuntimeError("cannot create demo room")
    return render_scene_json(world.snapshot())


def validate_turn(obj: object) -> tuple[str, str, list[dict[str, str]]]:
    if type(obj) is not dict or set(obj) != {"target", "message", "context"}:
        raise ValueError("expected exactly target, message, context")
    target, msg, history = obj["target"], obj["message"], obj["context"]
    if type(target) is not str or target not in SYSTEM:
        raise ValueError("unknown local slot")
    if type(msg) is not str or not 0 < len(msg.strip()) <= MAX_MESSAGE:
        raise ValueError("message must contain 1-2000 characters")
    if type(history) is not list or len(history) > MAX_CONTEXT:
        raise ValueError("context too long")
    for item in history:
        if (type(item) is not dict or set(item) != {"speaker", "text"}
                or type(item["speaker"]) is not str
                or item["speaker"] not in ("human", "vera", "jack")
                or type(item["text"]) is not str
                or not 0 < len(item["text"]) <= MAX_MESSAGE):
            raise ValueError("invalid context item")
    return target, msg.strip(), history


def build_messages(target: str, msg: str, history: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM[target]}]
    for item in history:
        speaker = item["speaker"]
        if speaker == target:
            messages.append({"role": "assistant", "content": item["text"]})
        else:
            label = "Human" if speaker == "human" else speaker.upper() + " slot (unverified)"
            messages.append({"role": "user", "content": label + ": " + item["text"]})
    messages.append({"role": "user", "content": "Human or forwarded message: " + msg})
    return messages


def local_ollama(model: str, messages: list[dict[str, str]]) -> str:
    payload = json.dumps({"model": model, "messages": messages, "stream": False,
                          "think": False,  # Explicitly reserve output budget for visible chat.
                          "options": {"temperature": 0.5, "num_predict": 160,
                                      "num_ctx": 2048}, "keep_alive": 0}).encode("utf-8")
    req = Request("http://127.0.0.1:11434/api/chat", payload,
                  headers={"Content-Type": "application/json"}, method="POST")
    # Ignore proxy environment variables for this fixed loopback-only inference route.
    with build_opener(ProxyHandler({})).open(req, timeout=75) as response:
        result = json.load(response)
    text = result.get("message", {}).get("content")
    if type(text) is not str or not text.strip():
        raise ValueError("local inference returned no visible response")
    return text[:4000]


# Constant, audited child script. The user prompt is read from stdin; no text in argv.
# The child re-verifies both pinned file digests before executing trusted source
# or decoding the separately stored private JACK model.
JACK_STDIN_DRIVER = """
import hashlib
import json
from pathlib import Path
import sys

source, model_path, expected_source, expected_model = sys.argv[1:5]
source_bytes = Path(source).read_bytes()
model_bytes = Path(model_path).read_bytes()
if hashlib.sha256(source_bytes).hexdigest() != expected_source:
    raise SystemExit("native JACK source digest changed")
if hashlib.sha256(model_bytes).hexdigest() != expected_model:
    raise SystemExit("private JACK model digest changed")
scope = {"__name__": "jack_native_private_loader", "__file__": source}
exec(compile(source_bytes, source, "exec"), scope)
model = json.loads(model_bytes)
scope["validate_model"](model)
question = sys.stdin.read(4097)
if len(question) > 4096:
    raise SystemExit("question too long")
print(scope["generate"](model, question, seed=1, max_tokens=45))
"""


def native_jack_sample(source: str, expected_sha256: str,
                       model_path: str, expected_model_sha256: str,
                       messages: list[dict[str, str]]) -> str:
    """Opt-in, hash-gated JACK native CLI inference; no private model data is returned."""
    src = Path(source).resolve(strict=True)
    model = Path(model_path).resolve(strict=True)
    if src.name != "jack_model.py" or not src.is_file() or not model.is_file():
        raise ValueError("native JACK needs its source and private model file")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("native JACK source SHA-256 required")
    if hashlib.sha256(src.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("native JACK source hash mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_model_sha256):
        raise ValueError("native JACK model SHA-256 required")
    if hashlib.sha256(model.read_bytes()).hexdigest() != expected_model_sha256:
        raise ValueError("native JACK model hash mismatch")
    if any((parent / ".git").exists() for parent in (model.parent, *model.parents)):
        raise ValueError("JACK model artifact must stay outside Git")
    question = messages[-1]["content"] if messages else ""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", JACK_STDIN_DRIVER,
         str(src), str(model), expected_sha256, expected_model_sha256],
        input=question, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=25, check=True,
    )
    reply = result.stdout.strip()
    if not reply:
        raise ValueError("native JACK generated an empty response")
    return reply[:4000]


class RoomServer(HTTPServer):
    def __init__(self, models: dict[str, str], responder: Callable = local_ollama,
                 port: int = 8765,
                 preview_assets: dict[str, tuple[str, str]] | None = None):
        if set(models) != set(SYSTEM):
            raise ValueError("exactly vera and jack model tags required")
        self.models = {name: validate_model(tag) for name, tag in models.items()}
        self.preview_assets: dict[str, tuple[Path, str]] = {}
        for slot, binding in (preview_assets or {}).items():
            if slot not in SYSTEM or type(binding) is not tuple or len(binding) != 2:
                raise ValueError("unknown or malformed preview slot")
            path, digest = binding
            resolved = Path(path).resolve(strict=True)
            preview_asset_bytes(resolved, digest)  # Reject before binding the port.
            self.preview_assets[slot] = (resolved, digest)
        self.responder = responder
        self.scene = make_scene()
        super().__init__(("127.0.0.1", port), RoomHandler)


class RoomHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass  # Never log user/model conversation content.

    def allowed_request(self) -> bool:
        host = self.headers.get("Host", "")
        if host not in ("localhost:" + str(self.server.server_port),
                        "127.0.0.1:" + str(self.server.server_port)):
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in (
            "http://localhost:" + str(self.server.server_port),
            "http://127.0.0.1:" + str(self.server.server_port))

    def send(self, code: int, data: object, html: bool = False) -> None:
        body = data.encode("utf-8") if html else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html
                         else "application/json; charset=utf-8")
        self.send_header("Content-Security-Policy", "default-src 'none'; "
                         "script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_sandbox_asset(self, filename: str, media_type: str) -> None:
        # Only fixed server-authored paths from SANDBOX_ASSETS reach this method.
        asset = Path(__file__).with_name("sandbox_assets") / filename
        try:
            body = asset.read_bytes()
        except OSError:
            return self.send(503, {"error": "local sandbox asset unavailable"})
        self.send_response(200)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Security-Policy", "default-src 'none'; "
                         "script-src 'self'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_preview_glb(self, slot: str) -> None:
        binding = self.server.preview_assets.get(slot)
        if binding is None:
            return self.send(404, {"error": "preview not configured"})
        try:
            body = preview_asset_bytes(*binding)
        except (OSError, ValueError):
            return self.send(503, {"error": "preview asset unavailable or changed"})
        self.send_response(200)
        self.send_header("Content-Type", "model/gltf-binary")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self.allowed_request():
            return self.send(403, {"error": "loopback origin required"})
        if self.path == "/api/preview-assets":
            return self.send(200, {"previews": [
                {"slot": slot, "url": "/sandbox/previews/" + slot + ".glb",
                 "sha256": binding[1], "approval": "UNVERIFIED_EXPERIMENTAL_PREVIEW"}
                for slot, binding in sorted(self.server.preview_assets.items())
            ]})
        if self.path in ("/sandbox/previews/vera.glb",
                         "/sandbox/previews/jack.glb"):
            return self.send_preview_glb(self.path.split("/")[-1][:-4])
        if self.path in SANDBOX_ASSETS:
            return self.send_sandbox_asset(*SANDBOX_ASSETS[self.path])
        if self.path == "/":
            return self.send(200, HTML, html=True)
        if self.path == "/api/scene":
            return self.send(200, json.loads(self.server.scene))
        if self.path == "/healthz":
            return self.send(200, {"ok": True, "scope": "LOCAL_DEMO_ONLY"})
        return self.send(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self.allowed_request():
            return self.send(403, {"error": "loopback origin required"})
        if self.path != "/api/turn":
            return self.send(404, {"error": "not found"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.send(415, {"error": "JSON required"})
        length = self.headers.get("Content-Length", "")
        if not length.isascii() or not length.isdecimal():
            return self.send(411, {"error": "valid content length required"})
        n = int(length)
        if n > MAX_BODY:
            return self.send(413, {"error": "request too large"})
        try:
            obj = json.loads(self.rfile.read(n).decode("utf-8"))
            target, msg, history = validate_turn(obj)
        except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            return self.send(400, {"error": "invalid turn"})
        try:
            reply = self.server.responder(self.server.models[target],
                                          build_messages(target, msg, history))
        except (OSError, ValueError, TimeoutError, URLError, subprocess.SubprocessError):
            return self.send(503, {"error": "local inference unavailable"})
        if type(reply) is not str or not reply:
            return self.send(503, {"error": "local inference unavailable"})
        return self.send(200, {"slot": target, "reply": reply[:4000],
                               "status": "UNVERIFIED_MODEL_OUTPUT"})


def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-in, loopback-only local two-model room")
    parser.add_argument("--vera-model", required=True, help="Local Ollama tag; not canonical Vera")
    jack = parser.add_mutually_exclusive_group(required=True)
    jack.add_argument("--jack-model", help="Generic local Ollama test tag; not JACK")
    jack.add_argument("--jack-native-model", help="Absolute private JACK analytic JSON path")
    parser.add_argument("--jack-native-source", help="Trusted local jack_model.py source file")
    parser.add_argument("--jack-source-sha256", help="Exact vetted SHA-256 of jack_model.py")
    parser.add_argument("--jack-model-sha256", help="Expected SHA-256 of private JACK model JSON")
    for slot in ("vera", "jack"):
        parser.add_argument("--" + slot + "-preview-glb", help="Private experimental GLB; no canon approval")
        parser.add_argument("--" + slot + "-preview-sha256", help="Exact SHA-256 of preview GLB")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    if args.jack_native_model:
        if not args.jack_native_source or not args.jack_source_sha256 or not args.jack_model_sha256:
            parser.error("native JACK requires source, source SHA-256 and private model SHA-256")
        source, source_sha, model_file, model_sha = (
            args.jack_native_source, args.jack_source_sha256,
            args.jack_native_model, args.jack_model_sha256)
        # Fail before binding a port if source/model custody is not qualified.
        try:
            src = Path(source).resolve(strict=True)
            path = Path(model_file).resolve(strict=True)
            if src.name != "jack_model.py" or not src.is_file() or not path.is_file():
                raise ValueError("invalid native JACK source/model path")
            if not re.fullmatch(r"[0-9a-f]{64}", source_sha):
                raise ValueError("invalid JACK source SHA-256")
            if hashlib.sha256(src.read_bytes()).hexdigest() != source_sha:
                raise ValueError("JACK source SHA-256 mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", model_sha):
                raise ValueError("invalid private JACK model SHA-256")
            if hashlib.sha256(path.read_bytes()).hexdigest() != model_sha:
                raise ValueError("private JACK model SHA-256 mismatch")
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        def responder(tag: str, messages: list[dict[str, str]]) -> str:
            if tag == "jack-native-analytic:v1":
                return native_jack_sample(source, source_sha, model_file, model_sha, messages)
            return local_ollama(tag, messages)
        jack_tag = "jack-native-analytic:v1"
    else:
        if args.jack_native_source or args.jack_source_sha256 or args.jack_model_sha256:
            parser.error("native JACK source options require --jack-native-model")
        responder, jack_tag = local_ollama, args.jack_model
    preview_assets = {}
    for slot in ("vera", "jack"):
        path = getattr(args, slot + "_preview_glb")
        digest = getattr(args, slot + "_preview_sha256")
        if bool(path) != bool(digest):
            parser.error("preview GLB requires its matching SHA-256")
        if path:
            preview_assets[slot] = (path, digest)
    try:
        server = RoomServer({"vera": args.vera_model, "jack": jack_tag},
                            responder=responder, port=args.port,
                            preview_assets=preview_assets)
    except (OSError, ValueError) as exc:
        parser.error("experimental preview invalid or unavailable: " + str(exc))
    print("Local room: http://127.0.0.1:" + str(server.server_port)
          + " (unverified models; opt-in unapproved geometry only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
