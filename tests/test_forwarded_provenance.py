"""Synthetic source-attribution boundaries for manual local model forwarding."""
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from vera_habitat.local_room import RoomServer, build_messages, validate_turn


def post(server, payload):
    req=Request("http://127.0.0.1:"+str(server.server_port)+"/api/turn",
                method="POST",data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type":"application/json"})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_explicit_forward_preserves_unverified_source_without_system_role():
    history=[{"speaker":"vera","text":"Synthetic correction: the offer was optional."}]
    target,msg,ctx,source=validate_turn({"target":"jack","message":history[-1]["text"],
                                           "context":history,"forwarded_from":"vera"})
    assert source=="vera"
    messages=build_messages(target,msg,ctx,source)
    assert [m["role"] for m in messages]==["system","user","user"]
    assert messages[-1]["content"].startswith("Claimed VERA slot forward (unverified): ")
    assert messages[-1]["content"].endswith(history[-1]["text"])
    assert "Human or forwarded message:" not in messages[-1]["content"]


def test_legacy_human_request_still_preserves_human_attribution():
    target,msg,ctx,source=validate_turn({"target":"vera","message":"Correction: it was a question.",
                                           "context":[]})
    assert source is None
    messages=build_messages(target,msg,ctx,source)
    assert messages[-1]=={"role":"user","content":"Human message: Correction: it was a question."}


@pytest.mark.parametrize("payload",[
    {"target":"jack","message":"hello","context":[],"forwarded_from":"vera"},
    {"target":"jack","message":"hello","context":[{"speaker":"jack","text":"hello"}],"forwarded_from":"jack"},
    {"target":"jack","message":"hello","context":[{"speaker":"vera","text":"different"}],"forwarded_from":"vera"},
    {"target":"jack","message":"hello","context":[{"speaker":"vera","text":"hello"}],"forwarded_from":"system"},
    {"target":"jack","message":"hello","context":[{"speaker":"vera","text":"hello"}],"forwarded_from":True},
    {"target":"jack","message":"hello","context":[{"speaker":"vera","text":"hello"}],"forwarded_from":None},
    {"target":"jack","message":"hello","context":[{"speaker":"vera","text":"hello"}],"forwarded_from":"human"},
])
def test_untraceable_or_self_forwarded_claim_is_rejected(payload):
    with pytest.raises(ValueError):
        validate_turn(payload)


def test_http_source_claim_is_advisory_not_privileged():
    seen=[]
    room=RoomServer({"vera":"fake-vera:dev","jack":"fake-jack:dev"},
                    responder=lambda model,messages:seen.append((model,messages)) or "synthetic ack",port=0)
    worker=Thread(target=room.serve_forever,daemon=True);worker.start()
    try:
        history=[{"speaker":"vera","text":"Synthetic optional offer; not a demand."}]
        status,response=post(room,{"target":"jack","message":history[-1]["text"],
                                   "context":history,"forwarded_from":"vera"})
        assert status==200 and response["status"]=="UNVERIFIED_MODEL_OUTPUT"
        assert len(seen)==1 and seen[0][0]=="fake-jack:dev"
        assert seen[0][1][-1]["role"]=="user"
        assert seen[0][1][-1]["content"].startswith("Claimed VERA slot forward (unverified): ")
        status,_=post(room,{"target":"jack","message":history[-1]["text"],
                            "context":history,"forwarded_from":"jack"})
        assert status==400 and len(seen)==1
    finally:
        room.shutdown();room.server_close();worker.join(timeout=5)
