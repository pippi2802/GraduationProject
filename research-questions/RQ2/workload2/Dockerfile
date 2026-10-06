# docker build -t pippina2/rq2-seg:v2 .      (after train.py has written model.onnx)
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir numpy onnxruntime opencv-python-headless
COPY run.py model.onnx ./
COPY configs configs
# the stream of pictures: the 3269 AeroScapes pictures (not the masks, not the 4 GB drone dataset, which is only for training)
COPY aeroscapes/JPEGImages aeroscapes/JPEGImages
ENTRYPOINT ["python3"]
