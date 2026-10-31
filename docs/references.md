# Method and software references

The code, its configuration, and its tests define the behavior of this prototype. The following sources provide method context. Cite the particular dataset and software versions used in an experiment in addition to citing this repository.

- Kingma, D. P., & Ba, J. (2014). *Adam: A method for stochastic optimization*. arXiv. https://doi.org/10.48550/arXiv.1412.6980. The linked record also identifies its ICLR 2015 publication; the year here refers to the arXiv submission.
- McMahan, B., Moore, E., Ramage, D., Hampson, S., & Agüera y Arcas, B. (2017). Communication-efficient learning of deep networks from decentralized data. In *Proceedings of the 20th International Conference on Artificial Intelligence and Statistics* (Vol. 54, pp. 1273–1282). https://proceedings.mlr.press/v54/mcmahan17a.html. Algorithm 1 supplies the model-averaging reference. Local Adam is a separately stated variant.
- Sellier, J. M. (2023). On a quantum inspired approach to train machine learning models. *Applied AI Letters, 4*(4), e89. https://doi.org/10.1002/ail2.89. Sections 4.3–4.5 are the source locations for the scoped Lean analysis. This repository does not claim to reproduce the complete training method.

## Dataset sources

- [FLNET2023 source repository and dataset organization](https://github.com/nsol-nmsu/FML-Network).
- [CICDDoS2019 official dataset description](https://www.unb.ca/cic/datasets/ddos-2019.html).

## Tool documentation

- [scikit-learn cross-validation guidance](https://scikit-learn.org/stable/modules/cross_validation.html).
- [scikit-learn preprocessing and leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).
- [Lean installation](https://lean-lang.org/install/) and the pinned `lean-toolchain` file.
- [uv documentation](https://docs.astral.sh/uv/).

Dataset source terms, library licenses, and article copyrights remain separate from this repository's MIT license. Source PDFs and dependency source trees are not redistributed here.
