"""Trains the U-Net on both datasets and exports it to model.onnx, the only thing the worker needs. Run it before building the image.

    pip install tensorflow-cpu tf2onnx opencv-python-headless scikit-learn
    python3 train.py

Accuracy does not matter for this workload, only execution time: the two label sets are not aligned (AeroScapes ids are just
shifted by 23, so the model has 35 classes) and one epoch is enough.
"""
from multiprocessing.pool import ThreadPool
from pathlib import Path

import cv2
import numpy as np
import tensorflow as tf
import tf2onnx
from sklearn.model_selection import train_test_split

from model import H, W, build_unet

# (folder, pictures, masks, decode flag, label offset). Pictures are decoded at reduced size (drone 6000x4000 at 1/8, AeroScapes 1280x720 at 1/2), still >= H x W; run.py does the same.
SOURCES = [("archive/dataset/semantic_drone_dataset", "original_images", "label_images_semantic", cv2.IMREAD_REDUCED_COLOR_8, 0),
           ("aeroscapes", "JPEGImages", "SegmentationClass", cv2.IMREAD_REDUCED_COLOR_2, 23)]
EPOCHS, BATCH = 1, 4


def load(item):
    (root, pictures, masks, flag, offset), name = item
    img = cv2.imread(f"{root}/{pictures}/{name}.jpg", flag)
    img = cv2.cvtColor(cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)     # as in run.py
    mask = cv2.imread(f"{root}/{masks}/{name}.png", cv2.IMREAD_GRAYSCALE)
    return img, cv2.resize(mask, (W, H), interpolation=cv2.INTER_NEAREST) + offset


items = [(src, p.stem) for src in SOURCES for p in sorted(Path(src[0], src[1]).glob("*.jpg"))]
images, masks = map(np.stack, zip(*ThreadPool(8).map(load, items)))
print(f"{len(items)} pictures from {len(SOURCES)} datasets, {int(masks.max()) + 1} label ids")
train, val = train_test_split(range(len(items)), test_size=0.2, random_state=19)

model = build_unet()
model.compile("adam", tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True), metrics=["accuracy"])
model.fit(images[train], masks[train], batch_size=BATCH, epochs=EPOCHS, validation_data=(images[val], masks[val]), verbose=2)


@tf.function(input_signature=[tf.TensorSpec([1, H, W, 3], tf.float32, name="image")])
def predict(img):                                              # one picture in, class id of every pixel out
    return tf.argmax(model(img, training=False), axis=-1, output_type=tf.int64)


tf2onnx.convert.from_function(predict, input_signature=predict.input_signature, opset=17, output_path="model.onnx")
print("wrote model.onnx")
