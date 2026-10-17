# docker build -t pippina2/rq2-lidar:v1 .      (after prepare_scans.py has filled scans/ with KITTI scans)
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libegl1 libgl1 libusb-1.0-0 libidn2-0 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir numpy open3d
COPY run.py ./
COPY configs configs
# the stream of scans: KITTI Velodyne scans (float32 x, y, z, reflectance), see prepare_scans.py
COPY scans scans
ENTRYPOINT ["python3"]
