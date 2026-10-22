FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libegl1 libgl1 libusb-1.0-0 libidn2-0 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir numpy open3d
COPY run.py ./
COPY configs configs
# the stream of scans: KITTI Velodyne scans (float32 x, y, z, reflectance)
COPY scans scans
ENTRYPOINT ["python3"]
