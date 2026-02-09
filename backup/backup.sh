#!/usr/bin/env bash
set -euo pipefail

ts="$(date +'%Y-%m-%d_%H-%M-%S')"

: "${WORKDIR:=/work}"

# ---------- Read secrets safely ----------
# Prefer *_FILE (Docker secrets), fallback to env.
read_secret() {
  local var="$1"
  local filevar="${var}_FILE"
  if [[ -n "${!filevar:-}" ]] && [[ -f "${!filevar}" ]]; then
    cat "${!filevar}"
  else
    echo -n "${!var:-}"
  fi
}

SMB_USER="$(read_secret SMB_USER)"
SMB_PASS="$(read_secret SMB_PASS)"
SMB_DOMAIN="${SMB_DOMAIN:-wismain}"

if [[ -z "${SMB_USER}" || -z "${SMB_PASS}" ]]; then
  echo "ERROR: SMB credentials missing. Provide SMB_USER/SMB_PASS or SMB_USER_FILE/SMB_PASS_FILE."
  exit 1
fi

# ---------- Config ----------
# SMB share you used: \\isi.storwis.weizmann.ac.il\labs
SMB_HOST="${SMB_HOST:-isi.storwis.weizmann.ac.il}"
SMB_SHARE="${SMB_SHARE:-labs}"

# Base path on SMB:
# You created: Mics/database_backup/{postgress,elastic_search}
SMB_BASEDIR="${SMB_BASEDIR:-yizharlab/Mics/database_backup}"

# Postgres
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-mics_db}"
PGUSER="${PGUSER:-mics_user}"
PGPASSWORD="$(read_secret PGPASSWORD)"
export PGPASSWORD

# Elasticsearch
ES_URL="${ES_URL:-http://es01:9200}"
ES_REPO="${ES_REPO:-org_repo}"
ES_REPO_PATH="${ES_REPO_PATH:-/es_repo}"   # directory inside backup container (mounted volume)

mkdir -p "$WORKDIR/out" "$WORKDIR/out/postgres" "$WORKDIR/out/elasticsearch" "$ES_REPO_PATH"

echo "==== Backup run at $ts ===="

# ==========================================================
# 1) POSTGRES: pg_dump -> gz
# ==========================================================
pg_file="$WORKDIR/out/postgres/postgres_${PGDATABASE}_${ts}.sql.gz"
echo "[postgres] dumping to $pg_file"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  --format=plain --no-owner --no-privileges \
  | gzip -9 > "$pg_file"
echo "[postgres] done"

# ==========================================================
# 2) ELASTICSEARCH: ensure repo exists, create snapshot
# ==========================================================
echo "[elasticsearch] checking repo $ES_REPO"
repo_status="$(curl -sS -o /dev/null -w '%{http_code}' "${ES_URL}/_snapshot/${ES_REPO}")" || true
if [[ "$repo_status" == "404" ]]; then
  echo "[elasticsearch] creating repo $ES_REPO at $ES_REPO_PATH"
  curl -sS -X PUT "${ES_URL}/_snapshot/${ES_REPO}" \
    -H 'Content-Type: application/json' \
    -d "{\"type\":\"fs\",\"settings\":{\"location\":\"${ES_REPO_PATH}\",\"compress\":true}}" \
    | jq .
else
  echo "[elasticsearch] repo exists (http $repo_status)"
fi

snap="snap_${ts}"
echo "[elasticsearch] creating snapshot $snap"
curl -sS -X PUT "${ES_URL}/_snapshot/${ES_REPO}/${snap}?wait_for_completion=true" \
  -H 'Content-Type: application/json' \
  -d '{"indices":"*","include_global_state":true}' \
  | jq .

# Tar the repository directory (contains the snapshot data/metadata)
es_file="$WORKDIR/out/elasticsearch/elasticsearch_repo_${ts}.tar.gz"
echo "[elasticsearch] archiving repo dir to $es_file"
tar -C "$ES_REPO_PATH" -czf "$es_file" .
echo "[elasticsearch] done"

# ==========================================================
# 3) UPLOAD BOTH FILES TO SMB USING smbclient (non-interactive)
# ==========================================================

# Build temporary smbclient auth file (non-interactive)
creds="$(mktemp)"
chmod 600 "$creds"
cat > "$creds" <<EOF
username=${SMB_USER}
password=${SMB_PASS}
domain=${SMB_DOMAIN}
EOF

# (Optional but recommended) ensure folders exist
smbclient "//${SMB_HOST}/${SMB_SHARE}" -A "$creds" \
  -c "mkdir \"yizharlab\"; cd \"yizharlab\"; mkdir \"Mics\"; cd \"Mics\"; mkdir \"database_backup\"; cd \"database_backup\"; mkdir \"postgress\"; mkdir \"elastic_search\"" \
  >/dev/null 2>&1 || true

upload_one() {
  local local_file="$1"
  local remote_dir="$2"

  echo "[smb] uploading $(basename "$local_file") -> ${remote_dir}"
  smbclient "//${SMB_HOST}/${SMB_SHARE}" -A "$creds" \
    -c "cd \"${remote_dir}\"; put \"${local_file}\" \"$(basename "$local_file")\""
}

# Remote dirs (relative to share root)
upload_one "$pg_file" "${SMB_BASEDIR}/postgress"
upload_one "$es_file" "${SMB_BASEDIR}/elastic_search"

rm -f "$creds"
echo "==== Backup completed at $(date) ===="
