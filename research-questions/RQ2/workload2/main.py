import os
import random
import tensorflow as tf
from tensorflow.keras.utils import Sequence
from sklearn.model_selection import train_test_split
import cv2
import matplotlib.pyplot as plot
from tqdm import tqdm
import numpy as np
from model import multi_unet_model

# variables and constants
MAIN_DIR = '../input/semantic-drone-dataset/dataset/semantic_drone_dataset'
IMG_PATH = MAIN_DIR + '/original_images/'
MASK_PATH = MAIN_DIR + '/label_images_semantic/'

CLASSES = 23
H = 800
W = 1200

# load dataset and preprocessing
def read_image(img):
    '''
    Read the image and resize it to the desired size
    '''
    img = cv2.imread(img, cv2.IMREAD_COLOR)
    img = cv2.resize(img, (W, H))
    img = img/255.0
    img = img.astype(np.float32)
    return img


def read_mask(img):
    '''
    Read the mask (semantic segemntation of refernce) and resize it to the desired size'''
    img = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (W, H))
    img = img.astype(np.int32)
    return img


def tf_dataset(x,y, batch=4):
    '''
    Create a Tensorflow Dataset object from the input data and apply preprocessing
    '''
    dataset = tf.data.Dataset.from_tensor_slices((x,y)) # Dataset object from Tensorflow
    dataset = dataset.shuffle(buffer_size=100) 
    dataset = dataset.map(preprocess) # Applying preprocessing to every batch in the Dataset object
    dataset = dataset.batch(batch) # Determine atch-size
    dataset = dataset.repeat()
    dataset = dataset.prefetch(2) # Optimization
    return dataset
        

def preprocess(x,y):
    def f(x,y):
        x = x.decode()
        y = y.decode()
        image = read_image(x)
        mask = read_mask(y)
        return image, mask
    
    image, mask = tf.numpy_function(f,[x,y],[tf.float32, tf.int32])
    mask = tf.one_hot(mask, CLASSES, dtype=tf.int32)
    image.set_shape([H, W, 3])    # In the Images, number of channels = 3. 
    mask.set_shape([H, W, CLASSES])    # In the Masks, number of channels = number of classes. 
    return image, mask

# test tf dataset
def test_dataset(x, batch=1):
    dataset = tf.data.Dataset.from_tensor_slices(x)
    dataset = dataset.map(preprocess_test)
    dataset = dataset.batch(batch)
    dataset = dataset.prefetch(2)
    return dataset
        

def preprocess_test(x):
    def f(x):
        x = x.decode()
        image = read_image(x)
        return image
    
    image = tf.convert_to_tensor(tf.numpy_function(f, [x] , [tf.float32]))
    image = tf.reshape(image, (H, W, 3))    # In the Images, number of channels = 3.  
    return image

# Main execution
# Split dataset into training and validation sets
names = sorted([img for img in os.listdir(IMG_PATH) if img.endswith('.png')])

X_trainval, X_test = train_test_split(names, test_size=0.1, random_state=19)
X_train, X_val = train_test_split(X_trainval, test_size=0.2, random_state=19)

print(f"Train Size: {len(X_train)}")
print(f"Val Size:   {len(X_val)}")
print(f"Test Size:  {len(X_test)}")

# Helper function
def build_paths(files):
    imgs  = [os.path.join(IMG_PATH,  f"{f}.png") for f in files]
    masks = [os.path.join(MASK_PATH, f"{f}.png") for f in files]
    return imgs, masks

img_train, mask_train = build_paths(X_train)
img_val,   mask_val   = build_paths(X_val)
img_test,  mask_test  = build_paths(X_test)

# we do one image at a time to keep the RT format
batch_size = 1

train_dataset = tf_dataset(img_train, mask_train, batch = batch_size)
valid_dataset = tf_dataset(img_val, mask_val, batch = batch_size)

test_dataset = tf_dataset(img_test, mask_test, batch = batch_size)

train_steps = len(img_train)//batch_size
valid_steps = len(img_val)//batch_size

model = multi_unet_model()

history = model.fit(train_dataset,
          steps_per_epoch=train_steps,
          validation_data=valid_dataset,
          validation_steps=valid_steps,
          epochs=10 #just to check it works properly
         )
model.save("sematicSegmentation.h5")
model =  tf.keras.models.load_model('./semanticSegmentation.h5') 
test_ds = tf_dataset(img_test, mask_test, batch = batch_size)
model.evaluate(test_ds, steps=14)

pred = model.predict(test_dataset(img_test, batch = 1), steps=40)