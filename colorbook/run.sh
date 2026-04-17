#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# Load addon options from /data/options.json into env vars
export OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
export PRINTER_HOST="$(bashio::config 'printer_host')"
export PRINTER_PORT="$(bashio::config 'printer_port')"
export PRINTER_QUEUE="$(bashio::config 'printer_queue')"
export PAPER_SIZE="$(bashio::config 'paper_size')"
export IMAGE_SIZE="$(bashio::config 'image_size')"
export IMAGE_QUALITY="$(bashio::config 'image_quality')"
export AUTO_ACCEPT_DEFAULT="$(bashio::config 'auto_accept_default')"
export OPENAI_IMAGE_MODEL="$(bashio::config 'openai_image_model')"
export OPENAI_CHAT_MODEL="$(bashio::config 'openai_chat_model')"
export APP_LANGUAGE="$(bashio::config 'language')"

# Fall back to pre-provisioned OPENAI_TOKEN if openai_api_key option is empty
if [ -z "${OPENAI_API_KEY}" ] && [ -n "${OPENAI_TOKEN:-}" ]; then
  export OPENAI_API_KEY="${OPENAI_TOKEN}"
fi

# Persistent data directory
export DATA_DIR="/data"
mkdir -p "${DATA_DIR}/images"

bashio::log.info "Starting Colorbook on :8099 (language: ${APP_LANGUAGE:-en})"

exec gunicorn \
  --bind 0.0.0.0:8099 \
  --workers 2 \
  --threads 4 \
  --worker-class gthread \
  --timeout 180 \
  --access-logfile - \
  --error-logfile - \
  "app.main:app"
