#!/bin/bash
cd /root/daily-iptv || exit 1

echo "[+] Running Python script..."
/usr/bin/python3 -u ottocean_fetch.py

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
