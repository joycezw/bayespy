import itertools
import numpy as np
import scipy as sp
import scipy.linalg.decomp_cholesky as decomp
import scipy.linalg as linalg
import scipy.special as special
import scipy.spatial.distance as distance

import imp

import utils
imp.reload(utils)

from .variable import Variable
from .constant import Constant
from .dirichlet import Dirichlet

def Categorical(p, **kwargs):

    # Get the number of categories (static methods may need this)
    if np.isscalar(p) or isinstance(p, np.ndarray):
        n_categories = np.shape(p)[-1]
    else:
        n_categories = p.dims[0][0]

    # The actual categorical distribution node
    class _Categorical(Variable):

        ndims = (1,)

        @staticmethod
        def compute_phi_from_parents(u_parents):
            return [u_parents[0][0]]

        @staticmethod
        def compute_g_from_parents(u_parents):
            return 0

        @staticmethod
        def compute_u_and_g(phi, mask=True):
            # For numerical reasons, scale contributions closer to
            # one, i.e., subtract the maximum of the log-contributions.
            max_phi = np.max(phi[0], axis=-1, keepdims=True)
            p = np.exp(phi[0]-max_phi)
            sum_p = np.sum(p, axis=-1, keepdims=True)
            # Moments
            u0 = p / sum_p
            u = [u0]
            # G
            g = -np.log(sum_p) - max_phi
            g = np.squeeze(g, axis=-1)
            #print('Categorical.compute_u_and_g, g:', np.sum(g), np.shape(g), np.sum(max_phi))
            return (u, g)

        @staticmethod
        def compute_fixed_u_and_f(x):
            """ Compute u(x) and f(x) for given x. """

            # TODO: You could check that x has proper dimensions
            x = np.array(x, dtype=np.int)

            u0 = np.zeros((np.size(x), n_categories))
            u0[[np.arange(np.size(x)), x]] = 1
            f = 0
            return ([u0], f)

        @staticmethod
        def compute_message(index, u, u_parents):
            """ . """
            #print('message in categorical:', u[0])
            if index == 0:
                return [ u[0].copy() ]

        @staticmethod
        def compute_dims(*parents):
            """ Compute the dimensions of phi/u. """
            # Has the same dimensionality as the parent.
            return parents[0].dims

        def __init__(self, p, **kwargs):

            # Check for constant mu
            if np.isscalar(p) or isinstance(p, np.ndarray):
                p = ConstantDirichlet(p)

            # Construct
            super().__init__(p,
                             **kwargs)


        def random(self):
            raise NotImplementedError()

        def show(self):
            p = self.u[0] #np.exp(self.phi[0])
            #p /= np.sum(p, axis=-1, keepdims=True)
            print("%s ~ Categorical(p)" % self.name)
            print("  p = ")
            print(p)

    return _Categorical(p, **kwargs)