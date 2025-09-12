#!/bin/bash
cd /root/daily-iptv || exit 1

# Ensure API key is available for cron
export TWOCAPTCHA_KEY="c630365b8247b8ebe02f1d751e0ea27f"

LOGFILE="/root/daily-iptv/daily.log"

{
    echo "===== Run started at $(date) ====="

    echo "[+] Running Python script..."
    /usr/bin/python3 -u iptvore_fetch1.py

    echo "[+] Staging files for commit..."
    git add iptv_daily/*
    if ! git diff --cached --quiet; then
        git commit -m "Auto update $(date '+%Y-%m-%d %H:%M')"
    else
        echo "[+] No changes to commit."
    fi

    echo "[+] Pulling from remote (rebase)..."
    git pull --rebase origin main

    echo "[+] Pushing to GitHub..."
    git push origin main

    echo "[✓] Done."
    echo "===== Run finished at $(date) ====="
    echo ""
} >> "$LOGFILE" 2>&1

