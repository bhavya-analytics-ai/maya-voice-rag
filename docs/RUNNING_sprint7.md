
# Start all 3
bash ~/Desktop/start_maya.sh

# Stop all 3
pkill -f "uvicorn|ngrok"

# Restart
pkill -f "uvicorn|ngrok" && sleep 2 && bash ~/Desktop/start_maya.sh



# Start all
pkill -f "uvicorn|ngrok" && sleep 2 && bash ~/Desktop/start_maya.sh

# Stop all
pkill -f "uvicorn|ngrok"

# Start MAYA
cd ~/Desktop/chatbot-corona && nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/maya.log 2>&1 &

# Start YOLO
cd ~/Desktop/cv-sprint-yolo && nohup python3 -m uvicorn api_yolo:app --host 0.0.0.0 --port 8001 > /tmp/yolo.log 2>&1 &

# Start ngrok
ngrok http 8000

# Stop MAYA
pkill -f "uvicorn app:app"

# Stop YOLO
pkill -f "uvicorn api_yolo"

# Stop ngrok
pkill -f ngrok

# Check whats running
ps aux | grep -E "uvicorn|ngrok" | grep -v grep
