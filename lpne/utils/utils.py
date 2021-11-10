"""
Useful functions

"""
__date__ = "July - November 2021"


import numpy as np
import os
import warnings

from .data import load_features, save_labels


LFP_FN_SUFFIX = '_LFP.mat'
CHANS_FN_SUFFIX = '_CHANS.mat'
FEATURE_FN_SUFFIX = '.npy'
LABEL_FN_SUFFIX = '.npy'



def write_fake_labels(feature_dir, label_dir, n_label_types=2,
    label_format='.npy', seed=42):
    """
    Write fake behavioral labels.

    Parameters
    ----------
    feature_dir : str
    label_dir : str
    n_label_types : int, optional
    label_format : str, optional
    seed : int, optional
    """
    # Get filenames.
    feature_fns = get_feature_filenames(feature_dir)
    label_fns = get_label_filenames_from_feature_filenames(
            feature_fns,
            label_dir,
    )
    # Seed.
    if seed is not None:
        np.random.seed(seed)
    # For each file pair...
    for feature_fn, label_fn in zip(feature_fns, label_fns):
        # Make the appropiate number of labels and save them.
        features = load_features(feature_fn)
        n = len(features['power'])
        labels = np.random.randint(0,high=n_label_types,size=n)
        save_labels(labels, label_fn)
    # Undo the seed.
    if seed is not None:
        np.random.seed(None)


def get_lfp_filenames(lfp_dir):
    """
    Get the LFP filenames in the given directory.

    Raises
    ------
    * AssertionError if the feature directory doesn't exist.
    * UserWarning if there are no feature files.

    Paramters
    ---------
    lfp_dir : str
        LFP directory

    Returns
    -------
    lfp_fns : list of str
        Sorted list of LFP filenames
    """
    assert os.path.exists(lfp_dir), f"{lfp_dir} doesn't exist!"
    fns = [
            os.path.join(lfp_dir,fn) \
            for fn in sorted(os.listdir(lfp_dir)) \
            if fn.endswith(LFP_FN_SUFFIX)
    ]
    if len(fns) == 0:
        warnings.warn(f"No LFP files in {lfp_dir}!")
    return fns


def get_feature_filenames(feature_dir):
    """
    Get the feature filenames in the given directory.

    Raises
    ------
    * AssertionError if the feature directory doesn't exist.
    * UserWarning if there are no feature files.

    Parameters
    ----------
    feature_dir : str
        Feature directory.
    """
    assert os.path.exists(feature_dir), f"{feature_dir} doesn't exist!"
    fns = [
            os.path.join(feature_dir,fn) \
            for fn in sorted(os.listdir(feature_dir)) \
            if fn.endswith(FEATURE_FN_SUFFIX)
    ]
    if len(fns) == 0:
        warnings.warn(f"No feature files in {feature_dir}!")
    return fns


def get_label_filenames_from_feature_filenames(feature_fns, label_dir):
    """
    ...

    Raises
    ------
    *

    Parameters
    ----------
    feature_fns : list of str
        ...
    label_dir : str
        ...

    Returns
    -------
    label_fns : list of str
        Label filenames
    """
    return [
            os.path.join(label_dir, os.path.split(feature_fn)[-1]) \
            for feature_fn in feature_fns
    ]


def get_lfp_chans_filenames(lfp_dir, chans_dir):
    """
    Get the corresponding LFP and CHANS filenames.

    Parameters
    ----------
    lfp_dir : str
    chans_dir : str

    Returns
    -------
    lfp_filenames : list of str
        LFP filenames
    chans_filenames : list of str
        The corresponding CHANS filenames
    """
    assert os.path.exists(lfp_dir), f"{lfp_dir} doesn't exist!"
    assert os.path.exists(chans_dir), f"{chans_dir} doesn't exist!"
    lfp_fns = [
            os.path.join(lfp_dir,fn) \
            for fn in sorted(os.listdir(lfp_dir)) \
            if fn.endswith(LFP_FN_SUFFIX)
    ]
    if len(lfp_fns) == 0:
        warnings.warn(f"No LFP files in {lfp_fns}!")
    chans_fns = [
            os.path.join(chans_dir,fn) \
            for fn in sorted(os.listdir(chans_dir)) \
            if fn.endswith(CHANS_FN_SUFFIX)
    ]
    if len(chans_fns) == 0:
        warnings.warn(f"No CHANS files in {chans_dir}!")
    assert len(lfp_fns) == len(chans_fns), f"{len(lfp_fns)} != {len(chans_fns)}"
    for i in range(len(lfp_fns)):
        lfp_fn = os.path.split(lfp_fns[i])[-1][:-len(LFP_FN_SUFFIX)]
        chans_fn = os.path.split(chans_fns[i])[-1][:-len(CHANS_FN_SUFFIX)]
        assert lfp_fn == chans_fn, f"{lfp_fn} != {chans_fn}"
    return lfp_fns, chans_fns


def get_feature_label_filenames(feature_dir, label_dir):
    """
    Get the corresponding feature and label filenames.

    Parameters
    ----------
    feature_dir : str
    label_dir : str

    Returns
    -------
    feature_filenames : list of str
        Feature filenames
    label_filenames : list of str
        The corresponding label filenames
    """
    assert os.path.exists(feature_dir), f"{feature_dir} doesn't exist!"
    assert os.path.exists(label_dir), f"{label_dir} doesn't exist!"
    feature_fns = [
            os.path.join(feature_dir,fn) \
            for fn in sorted(os.listdir(feature_dir)) \
            if fn.endswith(FEATURE_FN_SUFFIX)
    ]
    if len(feature_fns) == 0:
        warnings.warn(f"No feature files in {feature_dir}!")
    label_fns = [
            os.path.join(label_dir,fn) \
            for fn in sorted(os.listdir(label_dir)) \
            if fn.endswith(LABEL_FN_SUFFIX)
    ]
    if len(label_fns) == 0:
        warnings.warn(f"No label files in {label_dir}!")
    assert len(feature_fns) == len(label_fns), \
            f"{len(feature_fns)} != {len(label_fns)}"
    for i in range(len(feature_fns)):
        feature_fn = os.path.split(feature_fns[i])[-1]
        label_fn = os.path.split(label_fns[i])[-1]
        assert feature_fn == label_fn, f"{feature_fn} != {label_fn}"
    return feature_fns, label_fns


def get_weights(labels, groups):
    """
    Get weights inversely proportional to the label and group frequency.

    The average weight is fixed at one.

    Parameters
    ----------
    labels : numpy.ndarray
        Label array
    groups : numpy.ndarray
        Group array

    Returns
    -------
    weights : numpy.ndarray
        Weights
    """
    assert len(labels) == len(groups), f"{len(labels)} != {len(groups)}"
    n = len(labels)
    assert n > 0, f"len(labels) <= 0"
    ids = np.array(labels) + (np.max(labels)+1) * np.array(groups)
    unique_ids = np.unique(ids)
    id_counts = [len(np.argwhere(ids==id).flatten()) for id in unique_ids]
    id_weights = n / (len(unique_ids) * np.array(id_counts))
    weights = np.zeros(len(labels))
    for id, weight in zip(unique_ids, id_weights):
        weights[np.argwhere(ids==id).flatten()] = weight
    return weights


def unsqueeze_triangular_array(arr, dim=0):
    """
    Transform a numpy array from condensed triangular form to symmetric form.

    Parameters
    ----------
    arr : numpy.ndarray
    dim : int
        Axis to expand

    Returns
    -------
    new_arr : numpy.ndarray
        Expanded array
    """
    n = int(round((-1 + np.sqrt(1 + 8*arr.shape[dim])) / 2))
    assert (n * (n+1)) // 2 == arr.shape[dim], \
            f"{(n * (n+1)) // 2} != {arr.shape[dim]}"
    arr = np.swapaxes(arr, dim, -1)
    new_shape = arr.shape[:-1] + (n,n)
    new_arr = np.zeros(new_shape, dtype=arr.dtype)
    for i in range(n):
        for j in range(i+1):
            idx = (i * (i+1)) // 2 + j
            new_arr[..., i, j] = arr[..., idx]
    dim_list = list(range(new_arr.ndim-2)) + [dim]
    dim_list = dim_list[:dim] + [-2,-1] + dim_list[dim+1:]
    new_arr = np.transpose(new_arr, dim_list)
    return new_arr


def squeeze_triangular_array(arr, dims=(0,1)):
    """


    """
    assert len(dims) == 2
    assert arr.ndims > np.max(dims)
    assert arr.shape[dims[0]] == arr.shape[dims[1]]
    n = arr.shape[dims[0]]
    raise NotImplementedError



if __name__ == '__main__':
    pass



###
