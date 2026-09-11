#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
python3 deploy/mac/run.py || { printf '\n연결을 완료하지 못했습니다. 위 안내를 확인해주세요.\n'; read -r -p 'Enter를 누르면 닫힙니다.'; }
