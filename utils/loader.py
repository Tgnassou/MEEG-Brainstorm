#!/usr/bin/env python

"""
This script is used to create dataloaders.

Usage: type "from model import <class>" to use class.
       type "from model import <function>" to use function.

Contributors: Ambroise Odonnat.
"""

import torch

import numpy as np

from torch.utils.data import DataLoader, TensorDataset


def pad_tensor(x, n_pads, dim):

    """
    Pad up to n_pads with lowest int value a given tensor on dimension dim .
    Args:
        x (tensor): Tensor to pad.
        n_pads (int): Size to pad to.
        dim (int):  Dimension to pad on.

    Eeturn:
        A new tensor padded to n_pads on dimension dim.
    """

    pad_size = list(x.shape)
    pad_size[dim] = n_pads-x.shape[dim]

    return torch.cat([torch.Tensor(x), torch.zeros(*pad_size)], dim=dim)


class PadCollate:

    """ Custom collate_fn that pads according to the longest sequence in
        a batch of sequences.
    """

    def __init__(self, dim=1):

        """
        Args:
            dim (int): Dimension to pad.
        """

        self.dim = dim

    def pad_collate(self, batch):

        """
        Args:
            batch (list): List of (tensor, label).

        Return:
            xs (tensor): Tensor of all data in batch after padding.
            ys (tensor): LongTensor of all labels in batch.
        """

        # Find longest sequence
        max_len = max(map(lambda x: x[0].shape[self.dim], batch))

        # Pad according to max_len
        data = map(lambda x: pad_tensor(x[0], n_pads=max_len, dim=self.dim),
                   batch)
        labels = map(lambda x: torch.tensor(x[1]), batch)

        # Stack all
        xs = torch.stack(list(data), dim=0)
        ys = torch.stack(list(labels), dim=0)

        return xs, ys

    def __call__(self, batch):
        return self.pad_collate(batch)


def get_dataloader(data, labels, batch_size, shuffle, num_workers):

    """ Get dataloader.

    Args:
        data (array): Array of trials of dimension
                     [n_trials x 1 x n_channels x n_time_points].
        labels (array): Corresponding labels.
        batch_size (float): Size of batches.
        shuffle (bool): If True, shuffle batches in dataloader.
        num_workers (float): Number of loader worker processes.

    Returns:
        dataloader (Dataloader): Dataloader of trials and labels batches.
    """

    # Get dataloader
    data, labels = torch.from_numpy(data), torch.from_numpy(labels)
    dataset = TensorDataset(data, labels)
    dataloader = DataLoader(dataset=dataset, batch_size=batch_size,
                            shuffle=shuffle, num_workers=num_workers)

    return dataloader


def get_pad_dataloader(data, labels, batch_size,
                       shuffle, num_workers):

    """ Get dataloaders with padding according to the highest
        number of channels in each batch of trials.

    Args:
        data (list): List of array of trials of dimension
                     [n_trials x 1 x n_channels x n_time_points].
        labels (list): List of corresponding array of labels.
        batch_size (float): Size of batches.
        shuffle (bool): If True, shuffle batches in dataloader.
        num_workers (float): Number of loader worker processes.

    Returns:
        dataloader (Dataloader): Dataloader of trials and labels batches.
    """

    # Get dataloader
    dataset = []
    for id in range(len(data)):
        for n_trial in range(data[id].shape[0]):
            dataset.append((data[id][n_trial], labels[id][n_trial]))
    dataloader = DataLoader(dataset=dataset, batch_size=batch_size,
                            shuffle=shuffle, num_workers=num_workers,
                            collate_fn=PadCollate(dim=1))

    return dataloader
