"""
Single-file Vercel web app for X CLI / X Agent.

Deploy with this file as app.py and requirements.txt containing:
    tweepy>=4.14.0

Set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET,
and/or X_BEARER_TOKEN in Vercel Environment Variables.

The UI provides the operations implemented by the original CLI:
whoami, post/reply, thread, delete, timeline, search, user, like,
unlike, retweet, and unretweet.
"""

import json
import os
from http.server import BaseHTTPRequestHandler

try:
    import tweepy
except ImportError:
    tweepy = None


def credentials():
    return {
        "api_key": os.environ.get("X_API_KEY"),
        "api_secret": os.environ.get("X_API_SECRET"),
        "access_token": os.environ.get("X_ACCESS_TOKEN"),
        "access_token_secret": os.environ.get("X_ACCESS_TOKEN_SECRET"),
        "bearer_token": os.environ.get("X_BEARER_TOKEN"),
    }


def get_client(require_write=False):
    if tweepy is None:
        raise RuntimeError("Tweepy is not installed. Add tweepy to requirements.txt.")

    c = credentials()
    oauth1 = all(
        [c["api_key"], c["api_secret"], c["access_token"], c["access_token_secret"]]
    )

    if require_write and not oauth1:
        raise RuntimeError(
            "Write access requires X_API_KEY, X_API_SECRET, "
            "X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET."
        )

    if not c["bearer_token"] and not oauth1:
        raise RuntimeError(
            "No X credentials configured. Add X_BEARER_TOKEN for read-only "
            "operations or the full OAuth 1.0a credential set for writes."
        )

    return tweepy.Client(
        bearer_token=c["bearer_token"],
        consumer_key=c["api_key"],
        consumer_secret=c["api_secret"],
        access_token=c["access_token"],
        access_token_secret=c["access_token_secret"],
        wait_on_rate_limit=True,
    )


def tweet_dict(t):
    if not t:
        return None
    return {
        "id": str(t.id),
        "text": t.text,
        "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
        "metrics": t.public_metrics or {},
    }


def user_dict(u):
    if not u:
        return None
    return {
        "id": str(u.id),
        "username": u.username,
        "name": u.name,
        "description": getattr(u, "description", None),
        "location": getattr(u, "location", None),
        "metrics": getattr(u, "public_metrics", None) or {},
    }


def execute(action, data):
    if action == "whoami":
        client = get_client()
        r = client.get_me(user_fields=["public_metrics", "description"])
        return {"user": user_dict(r.data)}

    if action == "post":
        text = str(data.get("text", "")).strip()
        if not text:
            raise ValueError("Post text is required.")
        kwargs = {"text": text}
        if data.get("reply_to"):
            kwargs["in_reply_to_tweet_id"] = str(data["reply_to"])
        r = get_client(True).create_tweet(**kwargs)
        return {"tweet": tweet_dict(r.data)}

    if action == "thread":
        raw = str(data.get("text", ""))
        parts = [p.strip() for p in raw.split("\n---\n") if p.strip()]
        if not parts:
            raise ValueError("Enter thread posts separated by a line containing only ---.")

        client = get_client(True)
        posted = []
        previous = None
        for text in parts:
            kwargs = {"text": text}
            if previous:
                kwargs["in_reply_to_tweet_id"] = previous
            r = client.create_tweet(**kwargs)
            previous = str(r.data["id"])
            posted.append({"id": previous, "text": text})
        return {"thread": posted}

    if action == "delete":
        tweet_id = str(data.get("tweet_id", "")).strip()
        if not tweet_id:
            raise ValueError("Tweet ID is required.")
        get_client(True).delete_tweet(tweet_id)
        return {"deleted": tweet_id}

    if action == "search":
        query = str(data.get("query", "")).strip()
        if not query:
            raise ValueError("Search query is required.")
        count = max(10, min(int(data.get("count", 10)), 100))
        r = get_client().search_recent_tweets(
            query=query,
            max_results=count,
            tweet_fields=["created_at", "public_metrics"],
        )
        return {"tweets": [tweet_dict(t) for t in (r.data or [])]}

    if action == "timeline":
        username = str(data.get("username", "")).strip().lstrip("@")
        if not username:
            raise ValueError("Username is required.")
        count = max(5, min(int(data.get("count", 10)), 100))
        client = get_client()
        u = client.get_user(username=username)
        if not u.data:
            raise ValueError("User not found.")
        r = client.get_users_tweets(
            u.data.id,
            max_results=count,
            tweet_fields=["created_at", "public_metrics"],
        )
        return {"user": user_dict(u.data), "tweets": [tweet_dict(t) for t in (r.data or [])]}

    if action == "user":
        username = str(data.get("username", "")).strip().lstrip("@")
        if not username:
            raise ValueError("Username is required.")
        r = get_client().get_user(
            username=username,
            user_fields=["public_metrics", "description", "location"],
        )
        if not r.data:
            raise ValueError("User not found.")
        return {"user": user_dict(r.data)}

    if action in {"like", "unlike", "retweet", "unretweet"}:
        tweet_id = str(data.get("tweet_id", "")).strip()
        if not tweet_id:
            raise ValueError("Tweet ID is required.")
        client = get_client(True)
        me = client.get_me()
        if not me.data:
            raise RuntimeError("Could not resolve authenticated user.")

        if action == "like":
            client.like(me.data.id, tweet_id)
        elif action == "unlike":
            client.unlike(me.data.id, tweet_id)
        elif action == "retweet":
            client.retweet(me.data.id, tweet_id)
        else:
            client.unretweet(me.data.id, tweet_id)

        return {"action": action, "tweet_id": tweet_id}

    raise ValueError("Unknown action.")


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>X Agent</title>
<style>
:root{--bg:#070707;--panel:#101010;--line:#252525;--text:#f5f5f5;--muted:#969696;--accent:#fff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#181818 0,#070707 42%,#050505 100%);color:var(--text);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}
.wrap{max-width:1100px;margin:auto;padding:34px 18px 60px}.top{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:28px}
.logo{font-weight:800;font-size:24px;letter-spacing:-.8px}.badge{font-size:12px;color:#bbb;border:1px solid var(--line);border-radius:999px;padding:6px 10px}
.grid{display:grid;grid-template-columns:220px 1fr;gap:18px}.panel{background:rgba(16,16,16,.92);border:1px solid var(--line);border-radius:18px;box-shadow:0 20px 60px #0008}
nav{padding:10px}.nav{width:100%;text-align:left;background:transparent;color:#aaa;border:0;border-radius:10px;padding:11px 12px;cursor:pointer;font-size:14px}.nav:hover,.nav.active{background:#202020;color:#fff}
main{padding:22px}.hero h1{margin:0 0 5px;font-size:32px;letter-spacing:-1.2px}.hero p{margin:0;color:var(--muted)}
.form{margin-top:22px;display:grid;gap:13px}.row{display:grid;grid-template-columns:1fr 1fr;gap:13px}
label{display:grid;gap:7px;color:#aaa;font-size:12px;text-transform:uppercase;letter-spacing:.08em}input,textarea,select{width:100%;background:#090909;color:#fff;border:1px solid #303030;border-radius:11px;padding:12px;font:inherit;outline:0}textarea{min-height:150px;resize:vertical}input:focus,textarea:focus{border-color:#666}
button.primary{background:#fff;color:#000;border:0;border-radius:11px;padding:12px 17px;font-weight:750;cursor:pointer}button.primary:hover{transform:translateY(-1px)}
#output{margin-top:22px;background:#070707;border:1px solid var(--line);border-radius:13px;padding:16px;min-height:130px;white-space:pre-wrap;overflow:auto;color:#ddd}
.hidden{display:none}.hint{font-size:12px;color:#777;margin-top:8px}.status{margin-top:10px;color:#aaa}
@media(max-width:750px){.grid{grid-template-columns:1fr}.row{grid-template-columns:1fr}.top{align-items:flex-start}}
</style>
</head>
<body>
<div class="wrap">
<header class="top"><div class="logo">X Agent</div><div class="badge">Single-file Vercel app</div></header>
<div class="grid">
<aside class="panel"><nav id="nav"></nav></aside>
<section class="panel"><main>
<div class="hero"><h1 id="title"></h1><p id="desc"></p></div>
<form class="form" id="form"></form>
<div id="status" class="status"></div>
<pre id="output">Ready.</pre>
</main></section>
</div>
</div>
<script>
const actions={
whoami:{title:"Account",desc:"Inspect the authenticated X account.",fields:[]},
post:{title:"Post",desc:"Publish a post or reply.",fields:[["text","textarea","Post text"],["reply_to","input","Reply to tweet ID (optional)"]]},
thread:{title:"Thread",desc:"Publish multiple posts. Separate posts with a line containing only ---.",fields:[["text","textarea","Thread content"]]},
delete:{title:"Delete",desc:"Delete a post you own.",fields:[["tweet_id","input","Tweet ID"]]},
search:{title:"Search",desc:"Search recent X posts.",fields:[["query","input","Search query"],["count","input","Count (10–100)","10"]]},
timeline:{title:"Timeline",desc:"Read a user's recent posts.",fields:[["username","input","Username"],["count","input","Count (5–100)","10"]]},
user:{title:"User",desc:"Look up an X profile.",fields:[["username","input","Username"]]},
like:{title:"Like",desc:"Like a post.",fields:[["tweet_id","input","Tweet ID"]]},
unlike:{title:"Unlike",desc:"Remove your like.",fields:[["tweet_id","input","Tweet ID"]]},
retweet:{title:"Repost",desc:"Repost a post.",fields:[["tweet_id","input","Tweet ID"]]},
unretweet:{title:"Undo repost",desc:"Undo a repost.",fields:[["tweet_id","input","Tweet ID"]]}
};
let current="whoami";
const nav=document.getElementById("nav");
Object.keys(actions).forEach(k=>{const b=document.createElement("button");b.className="nav";b.textContent=actions[k].title;b.onclick=()=>show(k);b.dataset.action=k;nav.appendChild(b)});
function show(k){
 current=k; document.querySelectorAll(".nav").forEach(x=>x.classList.toggle("active",x.dataset.action===k));
 const a=actions[k]; title.textContent=a.title;desc.textContent=a.desc;form.innerHTML="";
 a.fields.forEach(f=>{const l=document.createElement("label");l.textContent=f[2];let el=document.createElement(f[1]==="textarea"?"textarea":"input");el.name=f[0];el.placeholder=f[2];if(f[3])el.value=f[3];l.appendChild(el);form.appendChild(l)});
 const btn=document.createElement("button");btn.type="submit";btn.className="primary";btn.textContent=k==="whoami"?"Run":"Execute";form.appendChild(btn);output.textContent="Ready.";status.textContent="";
}
form.addEventListener("submit",async e=>{
 e.preventDefault();status.textContent="Working…";output.textContent="";
 const data=Object.fromEntries(new FormData(form).entries());
 if(data.count)data.count=Number(data.count);
 try{const r=await fetch("/api",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:current,...data})});const j=await r.json();if(!r.ok)throw new Error(j.error||"Request failed");output.textContent=JSON.stringify(j,null,2);status.textContent="Done."}catch(err){output.textContent=err.message;status.textContent="Request failed."}
});
show("whoami");
</script>
</body>
</html>"""


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, HTML, "text/html")
            return
        self._send(404, json.dumps({"error": "Not found"}))

    def do_POST(self):
        if self.path != "/api":
            self._send(404, json.dumps({"error": "Not found"}))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            result = execute(data.get("action"), data)
            self._send(200, json.dumps({"ok": True, **result}, default=str))
        except ValueError as e:
            self._send(400, json.dumps({"ok": False, "error": str(e)}))
        except Exception as e:
            self._send(500, json.dumps({"ok": False, "error": str(e)}))


app = handler
