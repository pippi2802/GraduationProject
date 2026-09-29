FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rt_video.py launch.py analyze.py replay.py ./

ENTRYPOINT ["python3", "launch.py"]
CMD ["/config/instances.json"]
