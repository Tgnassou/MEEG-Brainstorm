#!/usr/bin/env python

"""
This script is used to train and evaluate models.

Usage: type "from training import <class>" to use one of its classes.

Contributors: Ambroise Odonnat and Theo Gnassounou.
"""

import copy
import torch

import numpy as np

from sklearn.metrics import precision_score, recall_score
from sklearn.metrics import f1_score, accuracy_score
from torch import nn

from utils.mix_up import mixup_data, mixup_criterion
from utils.utils_ import get_next_batch


class make_model():

    def __init__(self,
                 model,
                 train_loader,
                 val_loader,
                 test_loader,
                 optimizer,
                 train_criterion,
                 val_criterion,
                 n_epochs,
                 patience=None,
                 average='weighted',
                 mix_up=False,
                 beta=0.2):

        """
        Args:
            model (nn.Module): Model.
            train_loader (Dataloader): Loader of EEG samples for training.
            val_loader (Dataloader): Loader of EEG samples for validation.
            test_loader (Dataloader): Loader of EEG samples for test.
            optimizer (optimizer): Optimizer.
            train_criterion (Loss): Loss function for training.
            val_criterion (Loss): Loss function for validation and test.
            n_epochs (int): Maximum number of epochs to run.
            patience (int): Indicates how many epochs without improvement
                            on validation loss to wait for
                            before stopping training.
            average (str): Type of averaging on the data.
            mix_up (bool): If True, applu mix-up strategy.
        """

        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.optimizer = optimizer
        self.train_criterion = train_criterion
        self.val_criterion = val_criterion
        self.n_epochs = n_epochs
        self.patience = patience
        self.average = average
        self.mix_up = mix_up
        self.beta = beta
        self.sigmoid = nn.Sigmoid()

    def _do_train(self,
                  model,
                  loaders,
                  optimizer,
                  criterion,
                  average):

        """
        Train model.
        Args:
            model (nn.Module): Model.
            loaders (Sampler): Loaders of EEG samples for training.
            optimizer (optimizer): Optimizer.
            criterion (Loss): Loss function.
            average (str): Type of averaging on the data.

        Returns:
            train_loss (float): Mean loss on the loaders.
            perf (float): Mean F1-score on the loaders.
        """

        # Training loop
        model.train()
        device = next(model.parameters()).device
        train_loss = list()
        all_preds, all_labels = list(), list()

        iter_loader = [iter(loader) for loader in loaders]

        # Loop on training samples
        for batch_x, batch_y in iter_loader[0]:
            if len(loaders) > 1:
                batch_x_list = [batch_x]
                batch_y_list = [batch_y]
                for id in range(len(loaders[1:])):
                    batch_x, batch_y = get_next_batch(id, iter_loader, loaders)
                    batch_x_list.append(batch_x)
                    batch_y_list.append(batch_y)
                batch_x = torch.cat(batch_x_list, dim=0)
                batch_y = torch.cat(batch_y_list, dim=0)
            batch_x = batch_x.to(torch.float).to(device=device)
            batch_y = batch_y.to(torch.float).to(device=device)

            # Optimizer
            optimizer.zero_grad()

            # Forward
            output, _ = model(batch_x)
            loss = criterion(output, batch_y)
            pred = self.sigmoid(output)

            # Backward
            loss.backward()
            optimizer.step()

            # Recover loss and prediction
            train_loss.append(loss.item())
            all_preds.append(pred.detach().cpu().numpy())
            all_labels.append(batch_y.detach().cpu().numpy())

        # Recover binary prediction
        y_pred = np.concatenate(all_preds)
        y_pred_binary = 1 * (y_pred > 0.5)
        y_true = np.concatenate(all_labels)

        # Recover mean loss and F1-score
        train_loss = np.mean(train_loss)
        perf = f1_score(y_true, y_pred_binary, average=average,
                        zero_division=1)

        return train_loss, perf

    def _do_mix_up_train(self,
                         model,
                         loaders,
                         optimizer,
                         criterion,
                         average,
                         beta):

        """
        Train model.
        Args:
            model (nn.Module): Model.
            loaders (Sampler): Loaders of EEG samples for training.
            optimizer (optimizer): Optimizer.
            criterion (Loss): Loss function.
            average (str): Type of averaging on the data.
            beta (float): Parameter of the Beta Law.

        Returns:
            train_loss (float): Mean loss on the loaders.
            perf (float): Mean F1-score on the loaders.
        """

        # Training loop
        model.train()
        device = next(model.parameters()).device
        train_loss = list()
        all_preds, all_labels, all_shuffle_labels = list(), list(), list()

        iter_loader = [iter(loader) for loader in loaders]

        # Loop on training samples
        for batch_x, batch_y in iter_loader[0]:
            if len(loaders) > 1:
                batch_x_list = [batch_x]
                batch_y_list = [batch_y]
                for id in range(len(loaders[1:])):
                    batch_x, batch_y = get_next_batch(id, iter_loader, loaders)
                    batch_x_list.append(batch_x)
                    batch_y_list.append(batch_y)
                batch_x = torch.cat(batch_x_list, dim=0)
                batch_y = torch.cat(batch_y_list, dim=0)
            batch_x = batch_x.to(torch.float).to(device=device)
            batch_y = batch_y.to(torch.float).to(device=device)

            # Optimizer
            optimizer.zero_grad()

            # Apply mix-up strategy
            mixed_batch_x, shuffle_batch_y, lambd = mixup_data(batch_x,
                                                               batch_y,
                                                               device,
                                                               beta)
            mixed_batch_x = mixed_batch_x.to(torch.float)
            shuffle_batch_y = shuffle_batch_y.to(torch.float)

            # Forward
            output, _ = model(mixed_batch_x)
            loss = mixup_criterion(criterion,
                                   output,
                                   batch_y,
                                   shuffle_batch_y,
                                   lambd)
            pred = self.sigmoid(output)

            # Backward
            loss.backward()
            optimizer.step()

            # Recover loss and prediction
            train_loss.append(loss.item())
            all_preds.append(pred.detach().cpu().numpy())
            all_labels.append(batch_y.detach().cpu().numpy())
            all_shuffle_labels.append(shuffle_batch_y.detach().cpu().numpy())

        # Recover binary prediction
        y_pred = np.concatenate(all_preds)
        y_pred_binary = 1 * (y_pred > 0.5)
        y_true = np.concatenate(all_labels)
        shuffle_y_true = np.concatenate(all_shuffle_labels)

        # Recover mean loss and F1-score
        train_loss = np.mean(train_loss)
        perf = (lambd * f1_score(y_true, y_pred_binary,
                                 average=average, zero_division=1)
                + (1-lambd) * f1_score(shuffle_y_true, y_pred_binary,
                                       average=average, zero_division=1))

        return train_loss, perf

    def _validate(self,
                  model,
                  loader,
                  criterion,
                  average):

        """
        Evaluate model on validation set.
        Args:
            model (nn.Module): Model.
            loader (Sampler): Loader EEG samples for validation.
            criterion (Loss): Loss function.
            average (str): Type of averaging on the data.

        Returns:
            val_loss (float): Mean loss on the loader.
            perf (float): Mean F1-score on the loader.
        """

        # Validation loop
        model.eval()
        device = next(model.parameters()).device

        val_loss = np.zeros(len(loader[0]))
        all_preds, all_labels = list(), list()

        # Loop in validation samples
        with torch.no_grad():
            for idx_batch, (batch_x, batch_y) in enumerate(loader[0]):
                batch_x = batch_x.to(torch.float).to(device=device)
                batch_y = batch_y.to(torch.float).to(device=device)

                # Forward
                output, _ = model.forward(batch_x)
                pred = self.sigmoid(output)

                # Recover loss and prediction
                loss = criterion(output, batch_y)
                val_loss[idx_batch] = loss.item()
                all_preds.append(pred.cpu().numpy())
                all_labels.append(batch_y.cpu().numpy())

        # Recover binary prediction
        y_pred = np.concatenate(all_preds)
        y_pred_binary = 1 * (y_pred > 0.5)
        y_true = np.concatenate(all_labels)

        # Recover mean loss and F1-score
        val_loss = np.mean(val_loss)
        perf = f1_score(y_true, y_pred_binary, average=average,
                        zero_division=1)

        return val_loss, perf

    def train(self):

        """ Training function.

        Returns:
            best_model (nn.Module): The model that led to the best prediction
                                    on the validation
                                    dataset.
        history (list): List of dictionnaries containing training history
                        (loss, accuracy, etc.).
        """

        history = list()
        best_val_loss = np.inf
        self.best_model = copy.deepcopy(self.model)
        print("epoch \t train_loss \t val_loss \t train_f1 \t val_f1")
        print("-" * 80)

        for epoch in range(1, self.n_epochs + 1):
            if self.mix_up:
                results = self._do_mix_up_train(self.model,
                                                self.train_loader,
                                                self.optimizer,
                                                self.train_criterion,
                                                self.average,
                                                self.beta)
                train_loss, train_perf = results
            else:
                train_loss, train_perf = self._do_train(self.model,
                                                        self.train_loader,
                                                        self.optimizer,
                                                        self.train_criterion,
                                                        self.average)
            val_loss, val_perf = self._validate(self.model,
                                                self.val_loader,
                                                self.val_criterion,
                                                self.average)

            history.append(
                {"epoch": epoch,
                 "train_loss": train_loss,
                 "val_loss": val_loss,
                 "train_perf": train_perf,
                 "valid_perf": val_perf
                 }
            )

            print(
                f"{epoch} \t {train_loss:0.4f} \t {val_loss:0.4f} \t"
                f"{train_perf:0.4f} \t {val_perf:0.4f}\n"
            )

            if val_loss < best_val_loss:
                print(f"Best val loss {best_val_loss:.4f} "
                      f"-> {val_loss:.4f}\n")
                best_val_loss = val_loss
                self.best_model = copy.deepcopy(self.model)
                waiting = 0
            else:
                waiting += 1

            # Early stopping
            if self.patience is None:
                self.best_model = copy.deepcopy(self.model)
            else:
                if waiting >= self.patience:
                    print(f"Stop training at epoch {epoch}")
                    print(f"Best val loss : {best_val_loss:.4f}\n")
                    break

        return history

    def score(self):

        # Compute performance on test set
        self.best_model.eval()
        device = next(self.best_model.parameters()).device

        all_preds, all_labels = list(), list()
        with torch.no_grad():
            for batch_x, batch_y in self.test_loader[0]:
                batch_x = batch_x.to(torch.float).to(device=device)
                batch_y = batch_y.to(torch.float).to(device=device)

                # Forward
                output, _ = self.best_model.forward(batch_x)
                pred = self.sigmoid(output)

                # Recover prediction
                all_preds.append(pred.cpu().numpy())
                all_labels.append(batch_y.cpu().numpy())

        # Recover binary prediction
        y_pred = np.concatenate(all_preds)
        y_pred_binary = 1 * (y_pred > 0.5)
        y_true = np.concatenate(all_labels)

        # Recover performances
        acc = accuracy_score(y_true, y_pred_binary)
        f1 = f1_score(y_true, y_pred_binary, average=self.average,
                      zero_division=1)
        precision = precision_score(y_true, y_pred_binary,
                                    average=self.average, zero_division=1)
        recall = recall_score(y_true, y_pred_binary, average=self.average,
                              zero_division=1)

        print("Performances on test")
        print("Acc \t F1 \t Precision \t Recall")
        print("-" * 80)
        print(
            f"{acc:0.4f} \t {f1:0.4f} \t"
            f"{precision:0.4f} \t {recall:0.4f}\n"
        )

        return (acc, f1, precision, recall)
