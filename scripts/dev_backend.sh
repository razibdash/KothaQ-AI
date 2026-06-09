#!/usr/bin/env bash
set -euo pipefail
cd backend
uvicorn app.main:app --reload --port 8000
