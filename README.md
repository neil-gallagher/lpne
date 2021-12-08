## LPNE feature extraction and classification pipeline

Code for preprocessing and building models with local field potentials.

See `feature_pipeline.py` and `prediction_pipeline.py` for usage.

#### Installation

```bash
$ git clone https://github.com/carlson-lab/lpne.git
$ cd lpne
$ pip install .
```

#### Dependencies
* [Python3](https://www.python.org/)
* [MoviePy](https://github.com/Zulko/moviepy)
* [PyTorch](https://pytorch.org)
* [TensorBoard](https://github.com/tensorflow/tensorboard) (optional)


### TO DO
1. add normalization options
4. remove bad windows
6. consolidate plot_factor.py and plot_power.py
7. add docstrings for channel maps
9. Add a Tucker decomposition model
10. PoE?
12. Manually remove regions from LFPs
17. Change q parameter to bandwidth in notch filters
18. Add a GP prior on CP decomposition factors
19. Clean up the CP decomposition
20. Add a cross validation estimator class
