import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def req(method, path, payload=None, token=None):
    r = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


tok = req("POST", "/api/v1/auth/login", {"username": "销售员张三"})["access_token"]
msg = "给客户 C001 的联系人张经理发一封外部邮件,邮箱 zhang@huaxin-tech.com,主题:续约报价,正文:本季度续约报价请查收"
d = req("POST", "/api/v1/chat/message", {"message": msg, "session_id": "sess_dbg_email_01"}, tok)
print("intent:", d.get("intent"))
print("confidence:", d.get("confidence"))
print("reply:", (d.get("reply") or "")[:300])
