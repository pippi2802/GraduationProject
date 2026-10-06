# Workload 2 - Semantic Segmentation
To test the procedure, we apply it to a second and different workload with unknown execution time. Semantic Segmentation represented a workload which could possibly require a larger amount of CPU time, with images of different quality and detail and tehrefore, useful for computing variation.

## Data
- `archive/`: drone dataset (400 pictures, 23 classes), used for training only.
- `aeroscapes/`: AeroScapes (Nigam, Huang, Ramanan, WACV 2018; 3269 pictures 1280x720, 12 classes). Used for training and as the stream of pictures of the experiment: `JPEGImages/` is copied into the image, so every job of a run gets a different picture (the 5000 jobs of a run go through the 3269 pictures about 1.5 times).
- Label ids of the two datasets are not aligned (AeroScapes ids are shifted by 23, 35 classes): model accuracy is not the goal, execution time is.

## How to execute it
1. Train the model (writes `model.onnx`, the only thing the worker needs):
```
pip install tensorflow-cpu tf2onnx opencv-python-headless scikit-learn
python3 train.py
```
2. Build the docker image and push (the tag in `pods/*.yaml` must match):
```
docker build -t pippina2/rq2-seg:v2 .
docker push pippina2/rq2-seg:v2
```
3. Run the experiment: only `run.py` runs on the worker (`python3 run.py configs/<single_core|multi_core>.json`, see its docstring).
   `period_ms: 0` = continuous flow (next picture as soon as the previous one has finished); set `period_ms` once the period is chosen.
```
kubectl apply -f pods/single_core_pod.yaml
OUT_ROOT=workload2/results workload/pull_results.sh single_core baseline    # from the RQ2 folder
```
   The pods reuse the names and paths of the video workload, so `workload/pull_results.sh` collects them. Results go to `workload2/results/<model>/<condition>/`.
