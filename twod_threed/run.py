from __future__ import print_function, absolute_import

import os
import time

import torch
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim

from twod_threed.src.model import LinearModel, weight_init
from twod_threed.src.datasets.human36m import Human36M

from utils.osutils import mkdir_p, isfile, isdir, join



def run(options):
    """
    Run the model on a dataset and save it

    Important options params:
    options.load: The file for the saved model
    options.data_dir: The input directory for data (2D poses) to pass through the network
    options.output_dir: The directory to store output predictions
    options.process_as_video: Whether to process the data input as a video, and then output it as a video too

    :param options: The options passed in by command line
    """
    # Unpack options
    model_file = options.load
    data_input_dir = options.data_dir
    data_output_dir = options.output_dir
    process_as_video = options.process_as_video

    # Run
    model = _load_model(model_file)
    dataset = _run_model(model, data_input_dir, process_as_video)
    _save_preds(dataset, data_output_dir)



def _load_model(model_file):
    """
    Load the PyTorch 2D to 3D pose model

    :param model_file: The file for the saved model
    :return: A PyTorch nn.Module object for the trained 2D pose to 3D pose network
    """
    # Make the model
    model = LinearModel()
    model = model.cuda()

    # Load weights + set in eval mode
    checkpoint = torch.load(model_file)
    model.load_state_dict(checkpoint['state_dict'])
    model.eval()

    return model



def _run_model(model, data_input_dir, process_as_video):
    """
    Run a trained model on an entire dataset

    :param model: PyTorch nn.Module object for the trained Stacked Hourglass network
    :param data_input_dir: Directory for the dataset to run network on
    :param process_as_video: If the data input is a video, and should be output as a 'video' too
    :return: PyTorch Dataset object of 2D pose predictions
    """
    # Load in the dictionary/dataset + make a blank dict for 3D pose predictions
    dataset = torch.load(data_input_dir)
    predictions = {}

    i = 0

    # Loop through all keys in dataset. Handle single images by unsqeezing and squeezing to simulate a "batch"
    for key in dataset:
        # Progress
        if i % 30 == 0:
            print("At " + str(i) + " out of " + str(len(dataset)) + " videos.")
        i += 1

        input_tensor = torch.Tensor(dataset[key])

        if process_as_video:
            predictions[key] = _run_model_video(model, input_tensor)
        else:
            predictions[key] = _run_model_single_image(model, input_tensor)

    return predictions



def _run_model_video(model, input_tensor):
    """
    If each input is a video (rather than a single frame), run the network on all of the frames
    independently, and aggregate the result in a torch.Tensor.

    :param model: PyTorch nn.Module object for the trained Stacked Hourglass network
    :param input_tensor: 4D tensor, (time, x, y, depth) indexed for a video
    :return: 3D tensor (time, joints, coords) for 2D joint predictions
    """
    frames = []
    for i in range(input_tensor.size()[0]):
        frames.append(_run_model_single_image(model, input_tensor[i]))
    return frames



def _run_model_single_image(model, input_tensor):
    """
    Takes a list of 2D joint coordinates for a single frame and runs the network to produce 3D joint coords

    :param model: The PyTorch model
    :param input_tensor: The 2dim PyTorch tensor containing the input joint coords
    :return: The 3D join coords predicted by the network
    """
    input_var = torch.autograd.Variable(input_tensor.unsqueeze(0).cuda(), volatile=True)
    output = model(input_var)
    return output[-1].data.cpu()



def _save_preds(dataset, data_output_dir):
    """
    Save the PyTorch Dataset of predictions to a file

    :param dataset: The PyTorch Dataset object of predictions
    :param data_output_dir: The filename for the file to save
    """
    # Make directory if it doesn't exists
    if not isdir(data_output_dir):
        mkdir_p(data_output_dir)

    # Just save the predictions in the correct place via PyTorch
    torch.save(dataset, data_output_dir+"/3dposes")


