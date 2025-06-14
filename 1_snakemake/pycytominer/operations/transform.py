"""
From https://github.com/shntnu/pycytominer/blob/e7ef835daac20813bb92e4bad28b0e79a60d368b/pycytominer/operations/transform.py

Transform observation variables by specified groups.

References
----------
.. [1] Kessy et al. 2016 "Optimal Whitening and Decorrelation" arXiv: https://arxiv.org/abs/1512.00809
"""

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler


class Spherize(BaseEstimator, TransformerMixin):
    """Class to apply a sphering transform (aka whitening) data in the base sklearn
    transform API. Note, this implementation is modified/inspired from the following
    sources:
    1) A custom function written by Juan C. Caicedo
    2) A custom ZCA function at https://github.com/mwv/zca
    3) Notes from Niranj Chandrasekaran (https://github.com/cytomining/pycytominer/issues/90)
    4) The R package "whitening" written by Strimmer et al (http://strimmerlab.org/software/whitening/)
    5) Kessy et al. 2016 "Optimal Whitening and Decorrelation" [1]_

    Attributes
    ----------
    epsilon : float
        fudge factor parameter
    center : bool
        option to center the input X matrix
    method : str
        a string indicating which class of sphering to perform
    """

    def __init__(self, epsilon=1e-6, center=True, method="ZCA"):
        """
        Parameters
        ----------
        epsilon : float, default 1e-6
            fudge factor parameter
        center : bool, default True
            option to center the input X matrix
        method : str, default "ZCA"
            a string indicating which class of sphering to perform
        """
        avail_methods = ["PCA", "ZCA", "PCA-cor", "ZCA-cor"]

        self.epsilon = epsilon
        self.center = center

        if method not in avail_methods:
            raise ValueError(
                f"Error {method} not supported. Select one of {avail_methods}")
        self.method = method

        # PCA-cor and ZCA-cor require center=True
        if self.method in ["PCA-cor", "ZCA-cor"] and not self.center:
            raise ValueError("PCA-cor and ZCA-cor require center=True")

    def fit(self, X, y=None):
        """Identify the sphering transform given self.X

        Parameters
        ----------
        X : pandas.core.frame.DataFrame
            dataframe to fit sphering transform

        Returns
        -------
        self
            With computed weights attribute
        """

        if self.method in ["PCA-cor", "ZCA-cor"]:
            # The projection matrix for PCA-cor and ZCA-cor is the same as the
            # projection matrix for PCA and ZCA, respectively, on the standardized
            # data. So, we first standardize the data, then compute the projection

            self.standard_scaler = StandardScaler().fit(X)
            variances = self.standard_scaler.var_
            if np.any(variances == 0):
                raise ValueError(
                    "Divide by zero error, make sure low variance columns are removed"
                )

            X = self.standard_scaler.transform(X)
        else:
            if self.center:
                self.mean_centerer = StandardScaler(with_mean=True,
                                                    with_std=False).fit(X)
                X = self.mean_centerer.transform(X)

        # Get the number of observations and variables
        n, d = X.shape

        # compute the rank of the matrix X
        r = np.linalg.matrix_rank(X)

        # If n < d, then rank should be equal to n - 1 (if centered) or n (if not centered)
        # If n >= d, then rank should be equal to d
        if not ((r == d) | (self.center & (r == n - 1)) | (not self.center &
                                                           (r == n))):
            raise ValueError(
                "Sphering is not supported when the data matrix X is not full rank."
                "Check for linear dependencies in the data and remove them.")

        # Get the eigenvalues and eigenvectors of the covariance matrix using SVD
        _, Sigma, Vt = np.linalg.svd(X, full_matrices=True)

        # if n <= d then Sigma has shape (n,) so it will need to be expanded to
        # d filled with the value r'th element of Sigma
        if n <= d:
            # Do some error checking
            if Sigma.shape[0] != n:
                error_msg = f"When n <= d, Sigma should have shape (n,) i.e. ({n}, ) but it is {Sigma.shape}. the call to `np.linalg.svd` in `pycytominer.transform.Spherize`"
                raise ValueError(error_msg)

            if r != n - 1:
                error_msg = (
                    f"When n <= d, the rank should be n - 1 i.e. {n - 1} but it is {r}."
                    "the call to `np.linalg.svd` in `pycytominer.transform.Spherize`"
                )
                raise ValueError(error_msg)

            Sigma = np.concatenate((Sigma[0:r], np.repeat(Sigma[r - 1],
                                                          d - r)))

        Sigma = Sigma + self.epsilon

        self.W = (Vt / Sigma[:, np.newaxis]).transpose() * np.sqrt(n - 1)

        # If ZCA, perform additional rotation
        if self.method in ["ZCA", "ZCA-cor"]:
            # Note: There was previously a requirement r==d otherwise the
            # ZCA transform would not be well defined. However, it later appeared
            # that this requirement was not necessary.

            self.W = self.W @ Vt

        # number of columns of self.W should be equal to that of X
        assert (
            self.W.shape[1] == X.shape[1]
        ), f"Error: W has {self.W.shape[1]} columns, X has {X.shape[1]} columns"

        if self.W.shape[1] != X.shape[1]:
            error_detail = (
                f"The number of columns of W should be equal to that of X."
                f"However, W has {self.W.shape[1]} columns, X has {X.shape[1]} columns."
                f"the call to `np.linalg.svd` in `pycytominer.transform.Spherize`"
            )
            raise ValueError(error_detail)

        return self

    def transform(self, X, y=None):
        """Perform the sphering transform

        Parameters
        ----------
        X : pd.core.frame.DataFrame
            Profile dataframe to be transformed using the precompiled weights
        y : None
            Has no effect; only used for consistency in sklearn transform API

        Returns
        -------
        pandas.core.frame.DataFrame
            Spherized dataframe
        """
        if self.method in ["PCA-cor", "ZCA-cor"]:
            X = self.standard_scaler.transform(X)
        else:
            if self.center:
                X = self.mean_centerer.transform(X)
        XW = X @ self.W
        return XW