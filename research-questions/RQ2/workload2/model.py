"""U-Net for semantic segmentation. The constants are the knobs of the execution time of one picture."""
from tensorflow import keras
from tensorflow.keras import layers

H, W = 256, 384      # input size (multiples of 2**DEPTH)
CLASSES = 35         # 23 drone-dataset ids + 12 AeroScapes ids (shifted by 23, see train.py)
BASE = 8             # filters of the first level: cost grows with H * W * BASE**2
DEPTH = 4            # down-sampling steps


def block(x, filters):
    for _ in range(2):
        x = layers.Conv2D(filters, 3, padding="same", use_bias=False)(x)
        x = layers.BatchNormalization()(x)
        x = layers.ReLU()(x)
    return x


def build_unet():
    inp = keras.Input((H, W, 3), name="image")                 # RGB, values 0..255
    x = layers.Rescaling(1 / 255)(inp)
    skips = []
    for level in range(DEPTH):                                 # encoder
        x = block(x, BASE * 2 ** level)
        skips.append(x)
        x = layers.MaxPool2D()(x)
    x = block(x, BASE * 2 ** DEPTH)
    for level in reversed(range(DEPTH)):                       # decoder
        x = layers.Conv2DTranspose(BASE * 2 ** level, 2, strides=2, padding="same")(x)
        x = layers.Concatenate()([x, skips[level]])
        x = block(x, BASE * 2 ** level)
    return keras.Model(inp, layers.Conv2D(CLASSES, 1)(x))
