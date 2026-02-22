#!/usr/bin/env bash

# Shared helper functions for deploy scripts.

require_option_value() {
  local option_name="$1"
  local option_value="${2:-}"
  if [[ -z "$option_value" || "$option_value" == -* ]]; then
    echo "Option $option_name requires a value" >&2
    return 1
  fi
}

split_owner_group() {
  local owner_group="$1"
  if [[ "$owner_group" == *:* ]]; then
    DEPLOY_SERVICE_USER="${owner_group%%:*}"
    DEPLOY_SERVICE_GROUP="${owner_group##*:}"
  else
    DEPLOY_SERVICE_USER="$owner_group"
    DEPLOY_SERVICE_GROUP="$owner_group"
  fi

  if [[ -z "$DEPLOY_SERVICE_USER" || -z "$DEPLOY_SERVICE_GROUP" ]]; then
    echo "Unable to determine service user/group from owner group: $owner_group" >&2
    return 1
  fi
}

deploy_sync_env_file() {
  local remote_host="$1"
  local remote_dir="$2"
  local owner_group="$3"
  local source_env_file="$4"
  local remote_staging_dir="$5"
  local remote_port="${6:-22}"
  local ssh_control_path="${7:-}"

  split_owner_group "$owner_group"

  if [[ ! -f "$source_env_file" ]]; then
    echo "Local source env file not found: $source_env_file" >&2
    return 1
  fi

  local -a ssh_args=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new)
  if [[ -n "$remote_port" ]]; then
    ssh_args=(-p "$remote_port" "${ssh_args[@]}")
  fi
  if [[ -n "$ssh_control_path" ]]; then
    ssh_args=(-S "$ssh_control_path" "${ssh_args[@]}")
  fi

  local rsync_ssh_cmd="ssh"
  if [[ -n "$remote_port" ]]; then
    rsync_ssh_cmd+=" -p $remote_port"
  fi
  if [[ -n "$ssh_control_path" ]]; then
    rsync_ssh_cmd+=" -S $ssh_control_path"
  fi
  rsync_ssh_cmd+=" -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

  echo "→ Preparing remote staging dir on $remote_host:$remote_staging_dir"
  ssh "${ssh_args[@]}" "$remote_host" \
    "mkdir -p '$remote_staging_dir' && chmod 700 '$remote_staging_dir'"

  echo "→ Uploading $source_env_file to $remote_host:$remote_staging_dir/.env.racknerd"
  rsync -az --progress -e "$rsync_ssh_cmd" \
    "$source_env_file" "$remote_host:$remote_staging_dir/.env.racknerd"

  echo "→ Promoting remote env files in $remote_dir"
  local promote_env_cmd
  printf -v promote_env_cmd "bash -lc %q" \
    "sudo mkdir -p '$remote_dir' && sudo cp '$remote_staging_dir/.env.racknerd' '$remote_dir/.env.racknerd' && sudo cp '$remote_dir/.env.racknerd' '$remote_dir/.env' && sudo chown '$DEPLOY_SERVICE_USER:$DEPLOY_SERVICE_GROUP' '$remote_dir/.env.racknerd' '$remote_dir/.env' && sudo chmod 600 '$remote_dir/.env.racknerd' '$remote_dir/.env'"
  ssh "${ssh_args[@]}" "$remote_host" "$promote_env_cmd"
}
