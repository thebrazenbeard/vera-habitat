"""Actual browser regression: long local model reply must forward with source claim."""
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from vera_habitat.local_room import RoomServer


def main():
    calls=[]
    long_reply="SYNTHETIC_OPTIONAL_OFFER_"+("x"*2500)
    def responder(model,messages):
        calls.append((model,messages))
        return long_reply if model=="fake-vera:dev" else "SYNTHETIC_JACK_ACK"
    room=RoomServer({"vera":"fake-vera:dev","jack":"fake-jack:dev"},
                    responder=responder,port=0)
    t=Thread(target=room.serve_forever,daemon=True)
    t.start()
    try:
        script=ROOT/"tests"/"manual_sandbox_long_forward.cjs"
        result=subprocess.run(["node",str(script),f"http://127.0.0.1:{room.server_port}"],
                              env=os.environ,capture_output=True,text=True,timeout=65)
        print("BROWSER_EXIT",result.returncode)
        print("STDOUT",result.stdout[-1400:])
        print("STDERR",result.stderr[-1400:])
        print("BACKEND_CALLS",len(calls))
        if result.returncode:
            raise AssertionError("Browser did not forward the long reply")
        assert len(calls)==2, "No extra/automatic backend invocations"
        assert [model for model,_ in calls]==["fake-vera:dev","fake-jack:dev"]
        last=calls[1][1]
        assert last[-1]["role"]=="user"
        assert last[-1]["content"].startswith("Claimed VERA slot forward (unverified): ")
        assert len(last[-1]["content"])<=2050
        assert len(last[-2]["content"])<=2050
        print("REAL_BROWSER_ROLE_AND_BOUNDED_CONTEXT_PASS")
    finally:
        room.shutdown();room.server_close();t.join(timeout=5)
        print("SERVER_CLOSED",not t.is_alive())

if __name__=="__main__":
    main()
