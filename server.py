"""Minimal stdlib HTTP server implementing the five challenge endpoints."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json, time, uuid, os
from bot import compose_template
from conversation_handlers import ConversationState, respond

START=time.time()
contexts={"category":{}, "merchant":{}, "customer":{}, "trigger":{}}
versions={}
conversations={}
META={
 "team_name": os.getenv("VERA_TEAM_NAME","Astra"),
 "team_members": ["Astra"],
 "model": os.getenv("VERA_MODEL","deterministic-context-composer"),
 "approach": "context-grounded trigger routing + deterministic composer + replay state machine",
 "contact_email": os.getenv("VERA_CONTACT",""),
 "version": "1.1.0",
 "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
}

class Handler(BaseHTTPRequestHandler):
    def _send(self,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/v1/healthz":
            self._send(200,{"status":"ok","uptime_seconds":round(time.time()-START,2),
                "contexts_loaded":{k:len(v) for k,v in contexts.items()}}); return
        if p=="/v1/metadata": self._send(200,META); return
        self._send(404,{"error":"not_found"})
    def _json(self):
        n=int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(n) or b"{}")
    def do_POST(self):
        p=urlparse(self.path).path
        try: data=self._json()
        except Exception as e: self._send(400,{"accepted":False,"reason":"invalid_json","details":str(e)}); return
        if p=="/v1/context":
            scope=data.get("scope"); cid=data.get("context_id"); ver=data.get("version"); payload=data.get("payload")
            if scope not in contexts or not cid or not isinstance(ver,int) or ver<1 or payload is None:
                self._send(400,{"accepted":False,"reason":"invalid_context","details":"scope/context_id/version>=1/payload required"}); return
            key=(scope,cid); current=versions.get(key,0)
            if ver<=current:
                self._send(409,{"accepted":False,"reason":"stale_version","current_version":current}); return
            contexts[scope][cid]=payload; versions[key]=ver
            now=time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime())+"Z"
            self._send(200,{"accepted":True,"ack_id":f"ack_{cid}_v{ver}","stored_at":now}); return
        if p=="/v1/tick":
            actions=[]
            for tid in data.get("available_triggers",[]) or []:
                t=contexts["trigger"].get(tid)
                if not t: continue
                mid=t.get("merchant_id") or _payload_id(t,"merchant_id")
                m=contexts["merchant"].get(mid)
                if not m: continue
                cid=t.get("customer_id") or _payload_id(t,"customer_id")
                c=contexts["customer"].get(cid) if cid else None
                cat=contexts["category"].get(m.get("category_slug"),{})
                out=compose_template(cat,t,m,c)
                conv="conv_"+uuid.uuid4().hex[:12]
                conversations[conv]=ConversationState(conv,mid,cid)
                conversations[conv].sent_bodies.append(out["body"])
                actions.append({"conversation_id":conv,"merchant_id":mid,"customer_id":cid,
                    "send_as":out["send_as"],"trigger_id":tid,"template_name":out["template_name"],
                    "template_params":out["template_params"],"body":out["body"],"cta":out["cta"],
                    "suppression_key":out["suppression_key"],"rationale":out["rationale"]})
            self._send(200,{"actions":actions}); return
        if p=="/v1/reply":
            cid=data.get("conversation_id")
            state=conversations.get(cid)
            if not state:
                state=ConversationState(cid or "conv_unknown",data.get("merchant_id","unknown"),data.get("customer_id"))
                conversations[cid or state.conversation_id]=state
            self._send(200,respond(state,data.get("message",""))); return
        self._send(404,{"error":"not_found"})
    def log_message(self,format,*args): return

def _payload_id(trigger,key):
    return (trigger.get("payload") or {}).get(key)

if __name__=="__main__":
    port=int(os.getenv("PORT","8080"))
    ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
