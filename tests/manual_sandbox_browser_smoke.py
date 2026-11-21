"""Run an actual local Three.js room acceptance test with synthetic responders."""
import subprocess
import os
import sys
from threading import Thread
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from vera_habitat.local_room import RoomServer

def run():
    if not os.getenv("HABITAT_BROWSER_BINARY"):
        raise RuntimeError("HABITAT_BROWSER_BINARY must be an installed browser path")
    calls=[]
    def respond(model,messages):
        calls.append(model)
        return "synthetic fake JACK reply" if model.startswith("fake-jack") else "synthetic fake Vera reply"
    room=RoomServer({"vera":"fake-vera:dev","jack":"fake-jack:dev"},responder=respond,port=0)
    thread=Thread(target=room.serve_forever,daemon=True);thread.start()
    try:
        url=f"http://127.0.0.1:{room.server_port}"
        test=str(ROOT/"tests"/"manual_sandbox_browser_smoke.cjs")
        result=subprocess.run(["node",test,url],capture_output=True,text=True,timeout=75,
                              env=os.environ)
        print("BROWSER_EXIT",result.returncode)
        if result.stdout:print(result.stdout[-2000:])
        if result.stderr:print(result.stderr[-2200:])
        print("SERVER_MODEL_CALLS",calls)
        assert calls==["fake-vera:dev","fake-jack:dev"],"Automatic/incorrect model routing"
        assert result.returncode==0,"Browser sandbox acceptance failed"
        # Independent visual oracle: inspect screenshot pixels, not the WebGL
        # front buffer (which may be cleared after presenting a frame).
        from PIL import Image, ImageStat
        image_path=Path(os.environ["HABITAT_SCREENSHOT_PATH"])
        with Image.open(image_path) as picture:
            rgb=picture.convert("RGB")
            area=rgb.crop((130,180,min(800,rgb.width-350),min(600,rgb.height-50)))
            colors=len(area.getcolors(maxcolors=2000000) or [])
            variation=max(ImageStat.Stat(area).stddev)
            assert colors>80 and variation>7, "3D screenshot appears blank"
            print("VISUAL_PIXEL_ORACLE_PASS", {"colors":colors,"max_stddev":round(variation,2)})
    finally:
        room.shutdown();room.server_close();thread.join(timeout=5)
        print("SERVER_CLOSED",not thread.is_alive())
if __name__=="__main__":run()
