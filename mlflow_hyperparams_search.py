import math
import os
import tempfile
import shutil
import numpy as np
from keras.preprocessing.image import ImageDataGenerator
from keras.callbacks import ModelCheckpoint, EarlyStopping, TensorBoard
from snsdl.evaluation import Eval
from snsdl.keras.wrappers import MlflowClassifier
from myModels.shallownet import ShallowNet

# User-defined parameters
imageW = 64
imageH = 64
batch_size = 32

# Image Generators
idg = ImageDataGenerator(rescale=1. / 255)

train_generator = idg.flow_from_directory(
    directory="/tmp/dataset/output/train",
    target_size=(imageH, imageW),
    color_mode="rgb",
    batch_size=batch_size,
    class_mode="categorical",
    shuffle=True,
    seed=42
)

test_generator = idg.flow_from_directory(
    directory="/tmp/dataset/output/test",
    target_size=(imageH, imageW),
    color_mode="rgb",
    batch_size=batch_size,
    class_mode="categorical",
    shuffle=True,
    seed=42
)

val_generator = idg.flow_from_directory(
    directory="/tmp/dataset/output/val",
    target_size=(imageH, imageW),
    color_mode="rgb",
    batch_size=batch_size,
    class_mode="categorical",
    shuffle=True,
    seed=42
)

# Set callback functions to early stop training and save the best model so far
# callbacks = [[EarlyStopping(monitor='val_loss', patience=5), 
#                 ModelCheckpoint(filepath='/tmp/best_model.h5', monitor='val_loss', save_best_only=True)]]

callbacks = [[TensorBoard(log_dir='/tmp/tb')]]

# Space search
paramsSearch = {
    'input_shape':[(imageH, imageW, 3)],
    'num_classes':[train_generator.num_classes],
    'optimizer': ['adadelta'],
    'epochs': [2, 5],
    'callbacks': callbacks
}

# Custom model to train
myModel = ShallowNet(params=paramsSearch)

# Get all the combinations of the parameters
params = myModel.getSearchParams()

for p in params:

    artifacts_dir = tempfile.mkdtemp()

    # Create new classifier
    mlfc = MlflowClassifier(myModel.create_model, train_generator, test_generator, val_generator, artifacts_dir=artifacts_dir, **p)

    # Train the model
    history = mlfc.fit_generator()

    # Predict the test/val samples
    mlfc.predict_generator()

    # Predicted labels for test set
    y_predict = mlfc.getTestPredictLabels()

    # True labels of the test set
    y_true = mlfc.getTestTrueLabels()

    # Get the classes names
    class_names = mlfc.getClassNames()

    Eval.plot_history(history, png_output=os.path.join(artifacts_dir,'images'), show=False)
    Eval.full_multiclass_report(y_true, y_predict, class_names, png_output=os.path.join(artifacts_dir,'images'), show=False)

    # Classification Report
    Eval.classification_report(y_true, y_predict, output_dir=os.path.join(artifacts_dir, 'text'))

    # Wrong classifications
    Eval.wrong_predictions_report(test_generator.filenames, y_true, y_predict, os.path.join(artifacts_dir, 'text'))

    # Boxplot and report probabilities
    Eval.boxplot_report(test_generator.filenames, y_true, y_predict, mlfc.getTestPredictProbabilities(), class_names, boxplot_output=os.path.join(artifacts_dir,'images'), report_output=os.path.join(artifacts_dir,'text','probs'), show=False)

    # Log mlflow
    mlfc.log()

    # Clean up
    shutil.rmtree(artifacts_dir)
