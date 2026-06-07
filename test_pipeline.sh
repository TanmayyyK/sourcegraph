#!/bin/bash

echo "🎬 Creating test video..."
ffmpeg -f lavfi -i testsrc=s=320x240:d=5 -f lavfi -i sine=f=1000:d=5 \
  -pix_fmt yuv420p -c:v libx264 -c:a aac -y test_video.mp4 2>/dev/null

echo "📤 Uploading to pipeline..."
RESPONSE=$(curl -s -X POST http://localhost:8003/extract -F "video=@test_video.mp4")
JOB_ID=$(echo $RESPONSE | jq -r '.job_id')

echo "✅ Job ID: $JOB_ID"
echo ""
echo "📊 Live Status (polling every 2 seconds):"
echo ""

for i in {1..60}; do
  STATUS=$(curl -s http://localhost:8003/status/$JOB_ID)
  PIPELINE_STATUS=$(echo $STATUS | jq -r '.status')
  TOTAL_EVENTS=$(echo $STATUS | jq -r '.total_events')
  LAST_EVENT=$(echo $STATUS | jq -r '.log[-1]')
  
  echo "[$i] Status: $PIPELINE_STATUS | Events: $TOTAL_EVENTS"
  echo "    Last: $LAST_EVENT"
  echo ""
  
  if [ "$PIPELINE_STATUS" = "complete" ]; then
    echo "✅ PIPELINE COMPLETE!"
    echo ""
    echo "Full log:"
    echo $STATUS | jq '.log'
    break
  fi
  
  sleep 2
done