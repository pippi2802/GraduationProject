# Build from the RQ2 project ROOT (needs requirements.txt from there):
#   docker build -f workload/Dockerfile -t rq2-workload:latest .
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workload/rt_video.py workload/launch.py ./
COPY workload/configs configs
COPY workload/videos/sintel_720p_600.mp4 videos/sintel_720p_600.mp4

# The pod specs (workload/pods/*.yaml) always supply the full argv, so this
# is deliberately just the interpreter - there's no meaningful default CMD.
ENTRYPOINT ["python3"]
