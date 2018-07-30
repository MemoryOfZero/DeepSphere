# coding: utf-8

import os
import shutil
import sys

import numpy as np
from scnn import models, utils, experiment_helper
from scnn.data import LabeledDatasetWithNoise, LabeledDataset
from grid import pgrid


def single_experiment(sigma, order, sigma_noise):
    use_stat_layer = False
    Nside = 1024

    EXP_NAME = '40sim_{}sides_{}noise_{}order_{}sigma'.format(
        Nside, sigma_noise, order, sigma)

    x_raw_train, labels_raw_train, x_raw_std = experiment_helper.get_training_data(sigma, order)
    x_raw_test, labels_test, _ = experiment_helper.get_testing_data(sigma, order, sigma_noise, x_raw_std)

    ret = experiment_helper.data_preprossing(x_raw_train, labels_raw_train, x_raw_test, sigma_noise, feature_type=None)
    features_train, labels_train, features_validation, labels_validation, features_test = ret

    training = LabeledDatasetWithNoise(features_train, labels_train, start_level=0, end_level=sigma_noise, nit=len(labels_train) // 10 )
    validation = LabeledDataset(features_validation, labels_validation)

    if order == 4:
        nsides = [Nside, Nside // 2, Nside // 4, min(Nside // 8, 128)]
    elif order == 2:
        nsides = [
            Nside, Nside // 2, Nside // 4, Nside // 8,
            min(Nside // 16, 128)
        ]
    elif order == 1:
        nsides = [
            Nside, Nside // 2, Nside // 4, Nside // 8, Nside // 16,
            min(Nside // 32, 64)
        ]
    else:
        raise ValueError('No parameters for this value of order.')

    print('#sides: {}'.format(nsides))

    indexes = utils.nside2indexes(nsides, order)

    C = 2  # number of class
    ntrain = len(features_train)

    params = dict()
    params['dir_name'] = EXP_NAME

    # Building blocks.
    params['conv'] = 'chebyshev5'  # Convolution.
    params['pool'] = 'max'  # Pooling: max or average.
    params['activation'] = 'relu'  # Non-linearity: relu, elu, leaky_relu, etc.
    if use_stat_layer:
        params['statistics'] = 'meanvar'  # Compute statistics from feature maps to get invariance.
    else:
        params['statistics'] = None
    # Architecture.
    params['nsides'] = nsides  # Sizes of the laplacians are 12 * nsides**2.
    params['indexes'] = indexes  # Sizes of the laplacians are 12 * nsides**2.

    if order == 4:
        params['num_epochs'] = 80
        params['batch_size'] = 20
        params['F'] = [40, 160, 320, 20]  # Number of feature maps.
        params['K'] = [10] * 4  # Polynomial orders.
        params['batch_norm'] = [True] * 4  # Batch normalization.
        params['regularization'] = 2e-4
    elif order == 2:
        params['num_epochs'] = 250
        params['batch_size'] = 15
        params['F'] = [10, 80, 320, 40, 10]  # Number of feature maps.
        params['K'] = [10] * 5  # Polynomial orders.
        params['batch_norm'] = [True] * 5  # Batch normalization.
        params['regularization'] = 4e-4
    elif order == 1:
        params['num_epochs'] = 700
        params['batch_size'] = 10
        params['F'] = [10, 40, 160, 40, 20, 10]  # Number of feature maps.
        params['K'] = [10] * 6  # Polynomial orders.
        params['batch_norm'] = [True] * 6  # Batch normalization.
        params['regularization'] = 4e-4
    else:
        raise ValueError('No parameter for this value of order.')

    params['M'] = [100, C]  # Output dimensionality of fully connected layers.

    # Optimization.
    params['decay_rate'] = 0.98
    params['dropout'] = 0.5
    params['learning_rate'] = 1e-4
    params['momentum'] = 0.9
    params['adam'] = True
    params['decay_steps'] = 153.6
    params['use_4'] = False

    # Number of model evaluations during training.
    n_evaluations = 200
    params['eval_frequency'] = int(params['num_epochs'] * training.N / params['batch_size'] / n_evaluations)

    model = models.scnn(**params)

    # Cleanup before running again.
    shutil.rmtree('summaries/{}/'.format(EXP_NAME), ignore_errors=True)
    shutil.rmtree('checkpoints/{}/'.format(EXP_NAME), ignore_errors=True)

    accuracy, loss, t_step = model.fit(training, validation)

    error_validation = experiment_helper.model_error(model, features_validation, labels_validation)
    print('The validation error is {}%'.format(error_validation * 100), flush=True)

    error_test = experiment_helper.model_error(model, features_test, labels_test)
    print('The testing error is {}%'.format(error_test * 100), flush=True)

    return error_test


if __name__ == '__main__':

    if len(sys.argv) > 1:
        sigma = int(sys.argv[1])
        order = int(sys.argv[2])
        sigma_noise = float(sys.argv[3])
        grid = [(sigma, order, sigma_noise)]
    else:
        grid = pgrid()
    path = 'results/scnn/'

    os.makedirs(path, exist_ok=True)
    for p in grid:
        sigma, order, sigma_noise = p
        print('Launch experiment for {}, {}, {}'.format(sigma, order, sigma_noise))
        res = single_experiment(sigma, order, sigma_noise)
        filepath = os.path.join(path, 'scnn_results_list_sigma{}'.format(sigma))
        new_data = [order, sigma_noise, res]
        if os.path.isfile(filepath+'.npz'):
            results = np.load(filepath+'.npz')['data'].tolist()
        else:
            results = []
        results.append(new_data)
        np.savez(filepath, data=results)
