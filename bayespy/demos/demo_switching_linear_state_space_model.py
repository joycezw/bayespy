######################################################################
# Copyright (C) 2014 Jaakko Luttinen
#
# This file is licensed under Version 3.0 of the GNU General Public
# License. See LICENSE for a text of the license.
######################################################################

######################################################################
# This file is part of BayesPy.
#
# BayesPy is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# BayesPy is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BayesPy.  If not, see <http://www.gnu.org/licenses/>.
######################################################################

"""
Demonstrate switching linear state-space model
"""

import numpy as np
import matplotlib.pyplot as plt

from bayespy.nodes import (GaussianARD,
                           SwitchingGaussianMarkovChain,
                           CategoricalMarkovChain,
                           Dirichlet,
                           Mixture,
                           Gamma,
                           SumMultiply)

from bayespy.inference.vmp.vmp import VB
from bayespy.inference.vmp import transformations

import bayespy.plot.plotting as bpplt


def switching_linear_state_space_model(K=3, D=10, N=100, M=20):

    #
    # Switching dynamics (HMM)
    #

    # Prior for initial state probabilities
    rho = Dirichlet(1e-3*np.ones(K),
                    name='rho')

    # Prior for state transition probabilities
    V = Dirichlet(1e-3*np.ones(K),
                  plates=(K,),
                  name='V')
    V.initialize_from_value(10*np.identity(K) + 1*np.ones((K,K)))

    # Hidden states (with unknown initial state probabilities and state
    # transition probabilities)
    Z = CategoricalMarkovChain(rho, V,
                               states=N-1,
                               name='Z',
                               plotter=bpplt.CategoricalMarkovChainPlotter(),
                               initialize=False)
    Z.u[0] = np.random.dirichlet(np.ones(K))
    Z.u[1] = np.reshape(np.random.dirichlet(0.5*np.ones(K*K), size=(N-2)),
                        (N-2, K, K))

    #
    # Linear state-space models
    #

    # Dynamics matrix with ARD
    # (K,D) x ()
    alpha = Gamma(1e-5,
                  1e-5,
                  plates=(K,1,D),
                  name='alpha')
    # (K,1,1,D) x (D)
    A = GaussianARD(0,
                    alpha,
                    shape=(D,),
                    plates=(K,D),
                    name='A',
                    plotter=bpplt.GaussianHintonPlotter())
    A.initialize_from_value(np.identity(D)*np.ones((K,D,D))
                            + 0.1*np.random.randn(K,D,D))

    # Latent states with dynamics
    # (K,1) x (N,D)
    X = SwitchingGaussianMarkovChain(np.zeros(D),         # mean of x0
                                     1e-3*np.identity(D), # prec of x0
                                     A,                   # dynamics
                                     Z,                   # dynamics selection
                                     np.ones(D),          # innovation
                                     n=N,                 # time instances
                                     name='X',
                                     plotter=bpplt.GaussianMarkovChainPlotter())
    X.initialize_from_value(10*np.random.randn(N,D))

    # Mixing matrix from latent space to observation space using ARD
    # (K,1,1,D) x ()
    gamma = Gamma(1e-5,
                  1e-5,
                  plates=(D,),
                  name='gamma')
    # (K,M,1) x (D)
    C = GaussianARD(0,
                    gamma,
                    shape=(D,),
                    plates=(M,1),
                    name='C',
                    plotter=bpplt.GaussianHintonPlotter(rows=-3,cols=-1))
    C.initialize_from_value(np.random.randn(M,1,D))

    # Underlying noiseless function
    # (K,M,N) x ()
    F = SumMultiply('i,i', 
                    C, 
                    X,
                    name='F')
    
    #
    # Mixing the models
    #

    # Observation noise
    tau = Gamma(1e-5,
                1e-5,
                name='tau')
    tau.initialize_from_value(1e2)

    # Emission/observation distribution
    Y = GaussianARD(F, tau,
                    name='Y')

    Q = VB(Y, F,
           Z, rho, V,
           C, gamma, X, A, alpha,
           tau)

    return Q


def run_slssm(y, D, K, rotate=True, debug=False, maxiter=100, mask=True,
              monitor=False, update_hyper=0, autosave=None):
    
    (M, N) = np.shape(y)

    # Construct model
    Q = switching_linear_state_space_model(M=M, K=K, N=N, D=D)

    if autosave is not None:
        Q.set_autosave(autosave, iterations=10)

    Q['Y'].observe(y, mask=mask)

    # Set up rotation speed-up
    if rotate:
        # Initial rotate the D-dimensional state space (X, A, C)
        # Do not update hyperparameters
        rotA_init = transformations.RotateGaussianARD(Q['A'])
        rotX_init = transformations.RotateSwitchingMarkovChain(Q['X'],
                                                               Q['A'],
                                                               Q['Z'],
                                                               rotA_init)
        rotC_init = transformations.RotateGaussianARD(Q['C'])
        R_init = transformations.RotationOptimizer(rotX_init, rotC_init, D)
        # Rotate the D-dimensional state space (X, A, C)
        rotA = transformations.RotateGaussianARD(Q['A'], 
                                                 Q['alpha'])
        rotX = transformations.RotateSwitchingMarkovChain(Q['X'], 
                                                          Q['A'],
                                                          Q['Z'],
                                                          rotA)
        rotC = transformations.RotateGaussianARD(Q['C'],
                                                 Q['gamma'])
        R = transformations.RotationOptimizer(rotX, rotC, D)
        if debug:
            rotate_kwargs = {'maxiter': 10,
                             'check_bound': True,
                             'check_gradient': True}
        else:
            rotate_kwargs = {'maxiter': 10}

    # Run inference
    if monitor:
        Q.plot()
    for n in range(maxiter):
        if n < update_hyper:
            Q.update('X', 'C', 'A', 'tau', plot=monitor)
            if rotate:
                R_init.rotate(**rotate_kwargs)
        else:
            Q.update(plot=monitor)
            if rotate:
                R.rotate(**rotate_kwargs)

    return Q
    

def run(N=1000, maxiter=100, D=3, K=2, seed=42, plot=True, debug=False,
        rotate=True, monitor=True):

    # Use deterministic random numbers
    if seed is not None:
        np.random.seed(seed)

    #
    # Generate data
    #

    case = 2
    if case == 1:

        # Oscillation
        y0 = 5 * np.sin(0.02*2*np.pi * np.arange(N))
        # Random walk
        y1 = np.cumsum(np.random.randn(N))
        y = [y0, y1]

        # State switching probabilities
        q = 0.99        # probability to stay in the same state
        r = (1-q)/(2-1)  # probability to switch
        P = q*np.identity(2) + r*(np.ones((2,2))-np.identity(2))

        Y = np.zeros(N)
        z = np.random.randint(2)
        for n in range(1,N):
            Y[n] = y[z][n]
            z = np.random.choice(2, p=P[z])
        Y = Y[None,:]
            
    elif case == 2:

        # Two states: 1) oscillation, 2) random walk
        w1 = 0.02 * 2*np.pi
        A = [ [[np.cos(w1), -np.sin(w1)],
               [np.sin(w1),  np.cos(w1)]],
              [[        1.0,         0.0],
               [        0.0,         0.0]] ]
        C = [[1.0, 0.0]]

        # State switching probabilities
        q = 0.993        # probability to stay in the same state
        r = (1-q)/(2-1)  # probability to switch
        P = q*np.identity(2) + r*(np.ones((2,2))-np.identity(2))

        X = np.zeros((N, 2))
        Z = np.zeros(N)
        Y = np.zeros(N)
        F = np.zeros(N)
        z = np.random.randint(2)
        x = np.random.randn(2)
        Z[0] = z
        X[0,:] = x
        for n in range(1,N):
            x = np.dot(A[z], x) + np.random.randn(2)
            f = np.dot(C, x)
            y = f + 5*np.random.randn()
            z = np.random.choice(2, p=P[z])

            Z[n] = z
            X[n,:] = x
            Y[n] = y
            F[n] = f
            
        Y = Y[None,:]

    elif case == 3:

        # This experiment is from "Variational Learning for Switching
        # State-Space Models" (Ghahramani and Hinton)

        x0 = np.zeros(N)
        x0[0] = np.random.randn()
        for n in range(1,N):
            x0[n] = 0.99*x0[n-1] + np.random.randn()

        x1 = np.zeros(N)
        x1[0] = 10 * np.random.randn()
        for n in range(1,N):
            x1[n] = 0.9*x1[n-1] + np.sqrt(10)*np.random.randn()

        # State switching probabilities
        q = 0.95        # probability to stay in the same state
        r = (1-q)/(2-1)  # probability to switch
        P = 0.9*np.identity(2) + 0.05*np.ones((2,2))

        Y = np.zeros(N)
        z = np.random.randint(2)
        x = np.array([x0,x1])
        for n in range(N):
            y = x[z,n]
            z = np.random.choice(2, p=P[z])
            Y[n] = y
        Y = Y[None,:]
        

    if plot:
        plt.figure()
        bpplt.timeseries(F, 'b-')
        bpplt.timeseries(Y, 'rx')

    #
    # Use switching linear state-space model for inference
    #

    Q = run_slssm(Y, D, K, 
                  debug=debug,
                  maxiter=maxiter,
                  monitor=monitor,
                  rotate=rotate,
                  update_hyper=5)

    #
    # Show results
    #

    if plot:
        Q.plot()
        
    plt.show()
    

if __name__ == '__main__':
    import sys, getopt, os
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "",
                                   ["n=",
                                    "d=",
                                    "k=",
                                    "seed=",
                                    "debug",
                                    "no-rotation",
                                    "no-monitor",
                                    "maxiter="])
    except getopt.GetoptError:
        print('python demo_lssm.py <options>')
        print('--n=<INT>        Number of data vectors')
        print('--d=<INT>        Latent space dimensionality')
        print('--k=<INT>        Number of mixed models')
        print('--maxiter=<INT>  Maximum number of VB iterations')
        print('--seed=<INT>     Seed (integer) for the random number generator')
        print('--no-rotation    Do not peform rotation speed ups')
        print('--no-monitor     Do not plot distributions during VB learning')
        print('--debug          Check that the rotations are implemented correctly')
        sys.exit(2)

    kwargs = {}
    for opt, arg in opts:
        if opt == "--maxiter":
            kwargs["maxiter"] = int(arg)
        elif opt == "--d":
            kwargs["D"] = int(arg)
        elif opt == "--k":
            kwargs["K"] = int(arg)
        elif opt == "--seed":
            kwargs["seed"] = int(arg)
        elif opt == "--no-rotation":
            kwargs["rotate"] = False
        elif opt == "--no-monitor":
            kwargs["monitor"] = False
        elif opt == "--debug":
            kwargs["debug"] = True
        elif opt in ("--n",):
            kwargs["N"] = int(arg)
        else:
            raise ValueError("Unhandled option given")

    run(**kwargs)