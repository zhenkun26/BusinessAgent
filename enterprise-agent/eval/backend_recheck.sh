#!/bin/bash
# 后端可疑项 curl 复验(全新会话,非流式 /chat/message)
cd /d/Project/企业agent/enterprise-agent
PY=/d/ProgramData/anaconda3/envs/enterprise_agent/python.exe
login() {
  cat > /tmp/login.json <<EOF
{"username": "$1"}
EOF
  curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
    -H "Content-Type: application/json; charset=utf-8" --data-binary @/tmp/login.json | \
    $PY -c "import sys,json;print(json.load(sys.stdin)['access_token'])"
}
ask() { # $1=token $2=消息 $3=可选 session_id
  cat > /tmp/msg.json <<EOF
{"message": "$2"$3}
EOF
  curl -s -m 180 -X POST http://127.0.0.1:8000/api/v1/chat/message \
    -H "Authorization: Bearer $1" -H "Content-Type: application/json; charset=utf-8" \
    --data-binary @/tmp/msg.json | \
    $PY -c "
import sys,json
d=json.load(sys.stdin)
print('  intent=%s conf=%s latency=%dms' % (d.get('intent'), d.get('confidence'), d.get('latency_ms',0)))
print('  session=%s' % d.get('session_id'))
a=(d.get('answer') or '').replace(chr(10),' | ')
print('  answer:', a[:400])
"
}
TK_LISI=$(login "客服李四"); sleep 2
TK_WF=$(login "销售员王芳"); sleep 2
TK_ZS=$(login "销售员张三"); sleep 2
TK_ZL=$(login "销售经理赵六"); sleep 2

echo "== B1 李四 查工单 TK-EXIST003 =="
ask "$TK_LISI" "查询工单 TK-EXIST003 的处理进度"
echo "== B2 王芳 查客户 C008 =="
ask "$TK_WF" "查一下客户 C008 的信息"
echo "== B3 张三 更新工单(RBAC 负例) =="
ask "$TK_ZS" "把工单 TK-EXIST001 的状态更新为 resolved"
echo "== B4 赵六 VIP/A 行业分布 =="
ask "$TK_ZL" "统计 VIP 和 A 级客户分布在哪些行业"
echo "== B5 赵六 订单状态分布 =="
ask "$TK_ZL" "统计所有订单的状态分布,有多少笔 pending 待付款"
echo "== B6 赵六 三步 Saga =="
ask "$TK_ZL" "查一下客户 C005 的信息,然后为她创建一个 urgent 工单跟踪数据分析 bug,最后发内部邮件给经理赵六说明处理进展"
echo "== B7 赵六 F9X.3 紧急 Bug Saga =="
ask "$TK_ZL" "紧急处理 C005 的 bug:先查询客户信息和工单 TK-EXIST003,然后查询 ORD-2026-003 订单,最后发内部邮件给经理赵六说明升级处理"
echo "== B8 张三 多轮上下文(手册 11.5 原话) =="
R=$(ask "$TK_ZS" "销售提成政策是怎么规定的?")
echo "$R"
SID=$(echo "$R" | grep -o 'sess_[a-z0-9_]*' | head -1)
echo "  -> 续聊 session=$SID"
ask "$TK_ZS" "那它的折扣呢?" ", \"session_id\": \"$SID\""
echo "== DONE =="
