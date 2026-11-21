"""Browser acceptance for preserving a failed-send draft (synthetic, localhost only)."""
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from vera_habitat.local_room import RoomServer


def run():
    if not os.getenv("HABITAT_BROWSER_BINARY"):
        raise RuntimeError("Local browser binary is required")
    calls=[]
    def responder(model,messages):
        calls.append((model,messages))
        return "SYNTHETIC_FAKE_REPLY"
    room=RoomServer({"vera":"fake-vera:dev","jack":"fake-jack:dev"},
                    responder=responder,port=0)
    worker=Thread(target=room.serve_forever,daemon=True)
    worker.start()
    try:
        result=subprocess.run(["node",str(ROOT/"tests"/"manual_sandbox_draft_recovery.cjs"),
                               f"http://127.0.0.1:{room.server_port}"],
                              capture_output=True,text=True,timeout=75,env=os.environ)
        print("BROWSER_EXIT",result.returncode)
        print("BROWSER_STDOUT",result.stdout[-1000:])
        print("BROWSER_STDERR",result.stderr[-1100:])
        print("ACTUAL_BACKEND_MODEL_CALLS",len(calls))
        if result.returncode:
            raise AssertionError("Browser recovery test did not pass")
        if len(calls)!=2 or any(call[0]!="fake-vera:dev" for call in calls):
            raise AssertionError("Only two successful explicit user sends may reach the backend")
    finally:
        room.shutdown();room.server_close();worker.join(timeout=4)
        print("LOCAL_SERVER_CLOSED",not worker.is_alive())

if __name__=="__main__":
    run()
