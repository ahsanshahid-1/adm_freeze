#!/bin/bash
# Run the frozen formal stage to completion on the CRC server. Restarts the notebook session after an abnormal end
# (at most 4 attempts); completed runs are never redone because each session resumes from the stored run records.
# Stop everything with: kill -- -$(cat ~/Data-Mining/adm_crc_run/logs/formalrest.pid)
cd ~/Data-Mining || exit 1
NB=formal_session_rest.ipynb
for i in 1 2 3 4; do
  echo "[$(date '+%F %T')] attempt $i: starting session"
  ADM_PLATFORM=crc /opt/jupyterhub/bin/jupyter nbconvert --to notebook --execute \
    --ExecutePreprocessor.kernel_name=python3 --ExecutePreprocessor.timeout=-1 \
    --output "executed_formalrest_a${i}_$(date +%Y%m%d_%H%M).ipynb" "$NB"
  rc=$?
  st=$(/opt/jupyterhub/bin/python3 -c "import json; print(json.load(open('adm_crc_run/adm_state/STATE.json'))['stages'].get('formal'))")
  echo "[$(date '+%F %T')] attempt $i ended: exit $rc, formal stage = $st"
  if [ "$st" = "done" ]; then echo "FORMAL_COMPLETE"; exit 0; fi
  sleep 120
done
echo "GAVE_UP after 4 attempts"
exit 1
