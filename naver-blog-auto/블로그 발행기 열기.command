#!/bin/bash
# 더블클릭하면 블로그 자동 발행 대시보드를 켜고 브라우저로 열어요.
cd "$(dirname "$0")"
if ! curl -s -o /dev/null http://localhost:4000/api/status; then
  nohup node server.js > logs/server.log 2>&1 &
  sleep 1.5
fi
open http://localhost:4000
