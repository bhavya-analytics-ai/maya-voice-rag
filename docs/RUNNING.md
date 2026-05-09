# MAYA — Running & Stopping Guide

## What runs where

| Service | Port | What it does |
|---------|------|--------------|
| MAYA (FastAPI) | 8000 | Main chatbot — chat, image upload, voice |
| YOLO (FastAPI) | 8001 | Toilet brand detection for image uploads |
| ngrok | — | Public URL tunnel → forwards to port 8000 |

---

## Start everything (one command)

```bash
bash ~/Desktop/start_maya.sh
```

Starts MAYA + YOLO + prints the public ngrok URL.
> ngrok must be started separately (see below).

---

## Start individually

```bash
# 1. MAYA
cd ~/Desktop/chatbot-corona
nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/maya.log 2>&1 &

# 2. YOLO
cd ~/Desktop/cv-sprint-yolo
nohup python3 -m uvicorn api_yolo:app --host 0.0.0.0 --port 8001 > /tmp/yolo.log 2>&1 &

# 3. ngrok (public link)
ngrok http 8000
```

---

## Stop everything (one command)

```bash
pkill -f "uvicorn|ngrok"
```

---

## Stop individually

```bash
pkill -f "uvicorn app:app"    # stop MAYA
pkill -f "uvicorn api_yolo"   # stop YOLO
pkill -f ngrok                # stop tunnel
```

---

## Restart everything (one command)

```bash
pkill -f "uvicorn|ngrok" && sleep 2 && bash ~/Desktop/start_maya.sh
```

---

## Check what's running

```bash
ps aux | grep -E "uvicorn|ngrok" | grep -v grep
```

---

## Check logs

```bash
tail -f /tmp/maya.log    # MAYA logs
tail -f /tmp/yolo.log    # YOLO logs
tail -f /tmp/ngrok.log   # ngrok logs
```

---

## Health checks

```bash
curl http://localhost:8000/health   # MAYA → {"status":"ok","chain_loaded":true}
curl http://localhost:8001/         # YOLO → {"status":"API running"}
```

---

## Notes

- Your laptop must stay on and awake while sharing the ngrok link
- ngrok gives a new URL every time it restarts — resend the link to your friend
- If image upload stops working, YOLO is probably down — restart it with the individual command above
