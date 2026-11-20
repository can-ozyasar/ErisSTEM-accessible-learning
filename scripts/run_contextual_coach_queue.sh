#!/usr/bin/env bash
# Resume-safe contextual coach queue. Every question is generated and reviewed
# independently; a failure is logged and does not stop later question groups.
set -u

start=${1:?start offset required}
end=${2:?end offset required}
root_dir=$(cd "$(dirname "$0")/.." && pwd)
cd "$root_dir"
set -a
. ./.env
set +a

pack="data/private/ayt-history-exam/question-bank-training-candidate-v1.json"
log="data/private/ayt-history-exam/contextual-coach-queue.log"
for ((offset=start; offset<=end; offset++)); do
  draft="data/private/ayt-history-exam/contextual-coach-v3-$(printf '%03d' "$offset").json"
  review="data/private/ayt-history-exam/contextual-coach-review-v3-$(printf '%03d' "$offset").json"
  if [[ -f "$review" ]]; then
    printf 'skip reviewed offset=%s\n' "$offset" >> "$log"
    continue
  fi
  if apps/api/.venv/bin/python -m app.pipeline.deepseek_contextual_coach_drafts --pack "$pack" --output "$draft" --offset "$offset" --limit 1 --allow-external-private-evaluation >> "$log" 2>&1; then
    if apps/api/.venv/bin/python -m app.pipeline.deepseek_coaching_group_review --input "$draft" --output "$review" --offset 0 --limit 1 --allow-external-private-evaluation >> "$log" 2>&1; then
      printf 'completed offset=%s\n' "$offset" >> "$log"
    else
      printf 'review_failed offset=%s\n' "$offset" >> "$log"
    fi
  else
    printf 'draft_failed offset=%s\n' "$offset" >> "$log"
  fi
done
