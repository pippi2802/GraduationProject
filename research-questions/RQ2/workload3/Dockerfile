# docker build -t pippina2/rq2-audio:v1 . && docker push pippina2/rq2-audio:v1
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir numpy
COPY run.py .
# the audio stream: every .wav of audios/ (convert first, see run.py)
COPY audios/*.wav audios/
ENTRYPOINT ["python3"]
