"""
LPNE feature pipeline

Code for preprocessing and building factor models with local field potentials.

"""
__date__ = "July 2021 - November 2022"
__version__ = "0.1.10"
try:
    with open(".git/logs/HEAD", "r") as fh:
        __commit__ = fh.read().split("\n")[-2]
except:
    __commit__ = "unknown commit"

INVALID_LABEL = -1
INVALID_GROUP = -1

from .models import (
    FaSae,
    CpSae,
    GridSearchCV,
    DcsfaNmf,
    get_model_class,
    get_reconstruction_stats,
    get_reconstruction_summary,
)

from .plotting import (
    plot_db,
    plot_lfps,
    plot_factor,
    plot_factors,
    plot_power,
    plot_spec,
    make_power_movie,
)

from .preprocess.channel_maps import (
    IGNORED_KEYS,
    average_channels,
    get_excel_channel_map,
    get_default_channel_map,
    remove_channels,
    remove_channels_from_lfps,
    get_removed_channels_from_file,
)

from .preprocess.directed_spectrum import get_directed_spectrum

from .preprocess.filter import filter_signal, filter_lfps

from .preprocess.make_features import make_features

from .preprocess.normalize import normalize_features, normalize_lfps

from .preprocess.outlier_detection import mark_outliers


from .utils.array_utils import *

from .utils.data import (
    load_channel_map,
    load_features,
    load_features_and_labels,
    load_labels,
    load_lfps,
    save_features,
    save_labels,
)

from utils.file_utils import *

from .utils.utils import *

from .utils.viterbi import top_k_viterbi, get_label_stats


if __name__ == "__main__":
    pass


###
