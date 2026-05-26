#!/bin/bash
# ============================================
#  IVS - Internal Vibe Server (Stop)
# ============================================
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
echo "IVS stopped"
