"""
CANDECOMP/PARAFAC supervised autoencoder

TO DO:
* train with unobserved labels
"""
__date__ = "November 2021"


import numpy as np
import os
from sklearn.base import BaseEstimator
from sklearn.utils.validation import check_is_fitted
import torch
from torch.distributions import Categorical, Normal, kl_divergence
import torch.nn.functional as F
from torch.utils.data import TensorDataset, DataLoader, WeightedRandomSampler
import warnings

from ..utils.utils import get_weights, squeeze_triangular_array

# https://stackoverflow.com/questions/53014306/
if float(torch.__version__[:3]) >= 1.9:
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'


FLOAT = torch.float32
INT = torch.int64
MAX_LABEL = 1000
EPSILON = 1e-6
INVALID_LABEL = -1
FIT_ATTRIBUTES = ['classes_', 'groups_']



class CpSae(torch.nn.Module):

    def __init__(self, reg_strength=1.0, z_dim=32, group_embed_dim=2,
        weight_reg=0.0, data_kl_factor=1.0, n_iter=10000, lr=1e-3,
        batch_size=256, beta=0.5, group_kl_factor=1e-2, factor_reg=1e-2,
        device='auto'):
        """
        A supervised autoencoder with nonnegative and variational options.

        Parameters
        ----------
        reg_strength : float, optional
            This controls how much we weight the reconstruction loss. This
            should be positive, and larger values indicate more regularization.
        z_dim : int, optional
            Latent dimension/number of networks.
        weight_reg : float, optional
            Model L2 weight regularization.
        data_kl_factor : float, optional
            How much to weight the KL divergence term in the variational
            autoencoder (VAE). The standard setting is `1.0`. This is a distinct
            regularization parameter from `reg_strength` that can be
            independently set. This parameter is only used if `variational` is
            `True`.
        n_iter : int, optional
            Number of gradient steps during training.
        lr : float, optional
            Learning rate.
        batch_size : int, optional
            Minibatch size
        """
        super(CpSae, self).__init__()
        # Set parameters.
        self.reg_strength = float(reg_strength)
        self.z_dim = z_dim
        self.group_embed_dim = group_embed_dim
        self.weight_reg = float(weight_reg)
        self.data_kl_factor = float(data_kl_factor)
        self.n_iter = n_iter
        self.lr = float(lr)
        self.batch_size = batch_size
        self.beta = float(beta)
        self.group_kl_factor = float(group_kl_factor)
        self.factor_reg = float(factor_reg)
        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = device
        self.classes_ = None


    def _initialize(self, n_freqs, n_rois):
        """
        Initialize the network parameters.

        Parameters
        ----------
        n_freqs : int
        n_rois : int
        """
        self.n_groups = len(self.groups_)
        self.n_classes = len(self.classes_)
        n_features = n_freqs * n_rois**2
        self.group_mean = torch.nn.Parameter(
                torch.randn(self.n_groups, self.group_embed_dim),
        )
        self.group_log_std = torch.nn.Parameter(
                torch.randn(self.n_groups, self.group_embed_dim),
        )
        group_prior_mean = torch.zeros(self.group_embed_dim).to(self.device)
        group_prior_scale = torch.ones(self.group_embed_dim).to(self.device)
        self.group_prior = Normal(group_prior_mean, group_prior_scale)
        self.rec_model_1 = torch.nn.Linear(
                n_features + self.group_embed_dim,
                self.z_dim,
        )
        self.rec_model_2 = torch.nn.Linear(
                n_features + self.group_embed_dim,
                self.z_dim,
        )
        self.freq_net = torch.nn.Linear(
                self.group_embed_dim,
                self.z_dim * n_freqs,
        )
        self.roi_1_net = torch.nn.Linear(
            self.group_embed_dim,
            self.z_dim * n_rois,
        )
        self.roi_2_net = torch.nn.Linear(
            self.group_embed_dim,
            self.z_dim * n_rois,
        )
        self.logit_weights = torch.nn.Parameter(torch.randn(1,self.n_classes))
        self.logit_biases = torch.nn.Parameter(torch.randn(1,self.n_classes))
        prior_mean = torch.nn.Parameter(torch.zeros(self.z_dim)).to(self.device)
        prior_std = torch.ones(self.z_dim).to(self.device)
        self.prior = Normal(prior_mean, prior_std)
        self.logit_bias = torch.nn.Parameter(torch.zeros(1,self.n_classes))
        self.to(self.device)



    def fit(self, features, labels, groups, print_freq=100):
        """
        Fit the model to data.

        Parameters
        ----------
        features : [b,f,r,r]
        labels :
        groups :
        weights :
        print_freq :
        """
        # Check arguments.
        assert features.ndim == 4
        assert features.shape[2] == features.shape[3]
        assert labels.ndim == 1
        assert groups.ndim == 1
        assert len(features) == len(labels) and len(labels) == len(groups)
        # Initialize.
        weights = get_weights(labels, groups) # NOTE: here with invalid labels?
        idx = np.argwhere(labels == INVALID_LABEL)
        temp_label = np.unique(labels[labels != INVALID_LABEL])[0]
        labels[idx] = temp_label
        self.classes_, labels = np.unique(labels, return_inverse=True)
        labels[idx] = INVALID_LABEL
        assert len(self.classes_) > 1
        self.groups_, groups = np.unique(groups, return_inverse=True)
        assert len(self.groups_) > 1
        self._initialize(features.shape[1], features.shape[2])
        # NumPy arrays to PyTorch tensors.
        features = torch.tensor(features, dtype=FLOAT).to(self.device)
        labels = torch.tensor(labels, dtype=INT).to(self.device)
        groups = torch.tensor(groups, dtype=INT).to(self.device)
        weights = torch.tensor(weights, dtype=FLOAT).to(self.device)
        sampler_weights = torch.pow(weights, 1.0 - self.beta)
        weights = torch.pow(weights, self.beta)
        # Make some loaders and an optimizer.
        dset = TensorDataset(features, labels, groups, weights)
        sampler = WeightedRandomSampler(
                sampler_weights,
                num_samples=self.batch_size,
                replacement=True,
        )
        loader = DataLoader(
                dset,
                sampler=sampler,
                batch_size=self.batch_size,
        )
        optimizer = torch.optim.AdamW(
                self.parameters(),
                lr=self.lr,
                weight_decay=self.weight_reg,
        )
        # Train.
        for epoch in range(1,self.n_iter+1):
            epoch_loss = 0.0
            for batch in loader:
                self.zero_grad()
                loss = self(*batch)
                epoch_loss += loss.item()
                loss.backward()
                optimizer.step()
            if print_freq is not None and epoch % print_freq == 0:
                print(f"iter {epoch:04d}, loss: {loss:3f}")
        return self


    def _get_group_latents(self):
        std = EPSILON + torch.exp(self.group_log_std)
        group_dist = Normal(self.group_mean, std)
        return group_dist.rsample()


    def _project(self, zs, groups):
        """
        Project the latents to data space.

        Parameters
        ----------
        zs : [b,z]
        groups : [b]

        Returns
        -------
        volume : torch.Tensor
            Shape: [b,f,r,r]
        factor_loss : torch.Tensor
            Shape: []
        """
        # Sample from group distributions and get model factors.
        group_latents = self._get_group_latents() # [g,e]
        freq_f = F.softplus(self.freq_net(group_latents)) # [g,zf]
        freq_f = freq_f.view(self.n_groups, self.z_dim, -1) # [g,z,f]
        roi_1_f = F.softplus(self.roi_1_net(group_latents)) # [g,zr]
        roi_1_f = roi_1_f.view(self.n_groups, self.z_dim, -1) # [g,z,r]
        roi_2_f = F.softplus(self.roi_2_net(group_latents)) # [g,zr]
        roi_2_f = roi_2_f.view(self.n_groups, self.z_dim, -1) # [g,z,r]
        # Calculate a regularization term.
        mean_freq_f = torch.mean(freq_f, dim=0, keepdim=True)
        freq_loss = torch.pow(freq_f - mean_freq_f, 2).sum()
        mean_roi_1_f = torch.mean(roi_1_f, dim=0, keepdim=True)
        roi_1_loss = torch.pow(roi_1_f - mean_roi_1_f, 2).sum()
        mean_roi_2_f = torch.mean(roi_2_f, dim=0, keepdim=True)
        roi_2_loss = torch.pow(roi_2_f - mean_roi_2_f, 2).sum()
        # Make the volume.
        volume = torch.einsum(
                'bz,bzf,bzr,bzs->bfrs',
                F.softplus(zs),
                freq_f[groups],
                roi_1_f[groups],
                roi_2_f[groups],
        )
        return volume, freq_loss + roi_1_loss + roi_2_loss


    def _get_group_embed_loss(self):
        std = EPSILON + torch.exp(self.group_log_std)
        group_dist = Normal(self.group_mean, std)
        kld = kl_divergence(group_dist, self.group_prior).sum(dim=1) # [g]
        return kld.sum()


    @torch.no_grad()
    def _get_mean_projection(self):
        group_latents = self._get_group_latents() # [g,e]
        group_latents = torch.zeros_like(group_latents)
        freq_f = F.softplus(self.freq_net(group_latents)) # [g,zf]
        freq_f = freq_f.view(self.n_groups, self.z_dim, -1) # [g,z,f]
        roi_1_f = F.softplus(self.roi_1_net(group_latents)) # [g,zr]
        roi_1_f = roi_1_f.view(self.n_groups, self.z_dim, -1) # [g,z,r]
        roi_2_f = F.softplus(self.roi_2_net(group_latents)) # [g,zr]
        roi_2_f = roi_2_f.view(self.n_groups, self.z_dim, -1) # [g,z,r]
        freq_f = freq_f.mean(dim=0) # [z,f]
        roi_1_f = roi_1_f.mean(dim=0) # [z,r]
        roi_2_f = roi_2_f.mean(dim=0) # [z,r]
        volume = torch.einsum(
                'zf,zr,zs->zfrs',
                freq_f,
                roi_1_f,
                roi_2_f,
        )
        return volume


    def forward(self, features, labels, groups, weights):
        """
        Calculate a loss.

        Parameters
        ----------
        features : [b,f,r,r]
        labels : [b]
        groups : [b]
        weights : [b]

        Returns
        -------
        loss : torch.Tensor
            Shape: []
        """
        nan_mask = torch.isinf(1/(labels - INVALID_LABEL))
        labels[nan_mask] = 0
        # Augment features with group embeddings.
        flat_features = features.view(features.shape[0], -1)
        group_latents = self._get_group_latents() # [g,e]
        aug_features = torch.cat(
                [flat_features, group_latents[groups]],
                 dim=1,
        )

        # Feed through the recognition network to get latents.
        z_mus = self.rec_model_1(aug_features)
        z_log_stds = self.rec_model_2(aug_features)

        # Make the variational posterior and get a KL from the prior.
        dist = Normal(z_mus, EPSILON + z_log_stds.exp())
        kld = kl_divergence(dist, self.prior).sum(dim=1) # [b]

        # Sample latents.
        zs = dist.rsample() # [b,z]

        # Project.
        features_rec, factor_loss = self._project(zs, groups)
        flat_rec = features_rec.view(features.shape[0], -1)

        # Calculate a reconstruction loss.
        rec_loss = torch.mean((flat_features - flat_rec).pow(2), dim=1) # [b]

        # Predict the labels and get weighted label log probabilities.
        logits = zs[:,:self.n_classes] * F.softplus(self.logit_weights)
        logits = logits + self.logit_biases
        log_probs = Categorical(logits=logits).log_prob(labels) # [b]
        log_probs = weights * log_probs
        log_probs[nan_mask] = 0.0

        group_kld = self._get_group_embed_loss()

        # Combine all the terms into a composite loss.
        loss = -torch.mean(log_probs)
        loss = loss + self.reg_strength * torch.mean(rec_loss)
        loss = loss + self.data_kl_factor * torch.mean(kld)
        loss = loss + self.group_kl_factor * group_kld
        loss = loss + self.factor_reg * factor_loss
        return loss


    @torch.no_grad()
    def predict_proba(self, features, groups, to_numpy=True, stochastic=False):
        """
        Probability estimates.

        Note
        ----
        * This should be consistent with `self.forward`.

        Parameters
        ----------
        features : numpy.ndarray
            Shape: [b,f,r,r]
        groups : numpy.ndarray
            Shape: [b]
        to_numpy : bool, optional
        stochastic : bool, optional

        Returns
        -------
        probs : numpy.ndarray
            Shape: [batch, n_classes]
        """
        # Figure out the group mapping.
        temp_groups = np.unique(groups)
        new_groups = np.zeros_like(groups)
        group_list = self.groups_.tolist()
        for temp_group in temp_groups:
            try:
                new_groups[groups == temp_group] = group_list.index(temp_group)
            except:
                new_groups[groups == temp_group] = -1
        groups = new_groups
        # To PyTorch Tensors.
        features = torch.tensor(features, dtype=FLOAT).to(self.device)
        groups = torch.tensor(groups, dtype=INT).to(self.device)
        # Augment features with group embeddings.
        flat_features = features.view(features.shape[0], -1)
        group_latents = self._get_group_latents() # [g,e]
        latents = group_latents[groups]
        latents[groups == -1] = 0.0
        aug_features = torch.cat([flat_features, latents], dim=1)
        # Feed through the recognition network to get latents.
        zs = self.rec_model_1(aug_features)
        if stochastic:
            z_log_stds = self.rec_model_2(aug_features)
            dist = Normal(zs, EPSILON + z_log_stds.exp())
            zs = dist.rsample() # [b,z]
        logits = zs[:,:self.n_classes] * F.softplus(self.logit_weights)
        logits = logits + self.logit_biases
        probs = F.softmax(logits, dim=1) # [b, n_classes]
        if to_numpy:
            return probs.detach().cpu().numpy()
        return probs


    @torch.no_grad()
    def predict(self, features, groups):
        """
        Predict class labels for the features.

        Parameters
        ----------
        features : numpy.ndarray
            Shape: [b,f,r,r]
        groups : numpy.ndarray
            Shape: [b]

        Returns
        -------
        predictions : numpy.ndarray
            Shape: [b]
        """
        # Checks
        assert features.ndim == 4
        assert features.shape[2] == features.shape[3]
        check_is_fitted(self, attributes=FIT_ATTRIBUTES)
        # Feed through model.
        probs = self.predict_proba(features, groups, to_numpy=True)
        predictions = np.argmax(probs, axis=1)
        return self.classes_[predictions]


    @torch.no_grad()
    def score(self, features, labels, groups):
        """
        Get a class weighted accuracy.

        This is the objective we really care about, which doesn't contain the
        regularization in the `forward` method.

        Parameters
        ----------
        features : numpy.ndarray
            Shape: [b,f,r,r]
        labels : numpy.ndarray
            Shape: [b]
        groups : None or numpy.ndarray
            Shape: [b]

        Return
        ------
        weighted_acc : float
        """
        # Derive groups, labels, and weights from labels.
        weights = get_weights(labels, groups)
        predictions = self.predict(features, groups)
        scores = np.zeros(len(features))
        scores[predictions == labels] = 1.0
        scores = scores * weights
        weighted_acc = np.mean(scores)
        return weighted_acc


    def get_params(self, deep=True):
        """Get parameters for this estimator."""
        params = {
            'reg_strength': self.reg_strength,
            'z_dim': self.z_dim,
            'weight_reg': self.weight_reg,
            'data_kl_factor': self.data_kl_factor,
            'n_iter': self.n_iter,
            'lr': self.lr,
            'batch_size': self.batch_size,
            'beta': self.beta,
            'group_kl_factor': self.group_kl_factor,
            'factor_reg': self.factor_reg,
            'device': self.device,
            'classes_': self.classes_,
            'groups_': self.groups_,
        }
        if deep:
            params['model_state_dict'] = self.state_dict()
        return params


    def set_params(self, reg_strength=None, z_dim=None, weight_reg=None,
        data_kl_factor=None, n_iter=None, lr=None, batch_size=None, beta=None,
        group_kl_factor=None, factor_reg=None, device=None, classes_=None,
        groups_=None, model_state_dict=None):
        """
        Set the parameters of this estimator.

        Parameters
        ----------
        ...
        """
        if reg_strength is not None:
            self.reg_strength = reg_strength
        if z_dim is not None:
            self.z_dim = z_dim
        if weight_reg is not None:
            self.weight_reg = weight_reg
        if data_kl_factor is not None:
            self.data_kl_factor = data_kl_factor
        if n_iter is not None:
            self.n_iter = n_iter
        if lr is not None:
            self.lr = lr
        if batch_size is not None:
            self.batch_size = batch_size
        if beta is not None:
            self.beta = beta
        if group_kl_factor is not None:
            self.group_kl_factor = group_kl_factor
        if factor_reg is not None:
            self.factor_reg = factor_reg
        if device is not None:
            self.device = device
        if classes_ is not None:
            self.classes_ = classes_
        if groups_ is not None:
            self.groups_ = groups_
        if model_state_dict is not None:
            # n_freqs, n_rois
            assert 'freq_factors' in model_state_dict, \
                    f"'freq_factors' not in {list(model_state_dict.keys())}"
            n_freqs = model_state_dict['freq_factors'].shape[-1]
            assert 'roi_1_factors' in model_state_dict, \
                    f"'roi_1_factors' not in {list(model_state_dict.keys())}"
            n_rois = model_state_dict['roi_1_factors'].shape[-1]
            self._initialize(n_freqs, n_rois)
            self.load_state_dict(model_state_dict)
        return self


    def save_state(self, fn):
        """Save parameters for this estimator."""
        np.save(fn, self.get_params(deep=True))


    def load_state(self, fn):
        """Load and set the parameters for this estimator."""
        self.set_params(**np.load(fn, allow_pickle=True).item())


    @torch.no_grad()
    def get_factor(self, factor_num=0):
        """
        Get a linear factor.

        Parameters
        ----------
        feature_num : int
            Which factor to return. 0 <= `factor_num` < self.z_dim

        Returns
        -------
        factor : numpy.ndarray
            Shape: [r(r+1)/2,f]
        """
        check_is_fitted(self, attributes=FIT_ATTRIBUTES)
        assert isinstance(factor_num, int)
        assert factor_num >= 0 and factor_num < self.z_dim
        volume = self._get_mean_projection()[factor_num]  # [f,r,r]
        volume = volume.detach().cpu().numpy()
        volume = squeeze_triangular_array(volume, dims=(1,2))
        return volume.T



if __name__ == '__main__':
    pass



###
