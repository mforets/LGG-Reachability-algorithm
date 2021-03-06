r"""
Le Guernic-Girard Reachability Algorithm in Sage.

AUTHOR:

- Marcelo Forets (Dec 2016 at VERIMAG - France)
"""
#************************************************************************
#       Copyright (C) 2016 Marcelo Forets <mforets@nonlinearnotes.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# any later version.
#                  http://www.gnu.org/licenses/
#************************************************************************

#===============================================
# Dependencies
#===============================================

# Working numerical libraries
import numpy as np
import scipy
from scipy import inf
from scipy.io import savemat
import scipy.sparse as sp
from scipy.sparse import kron, eye
import scipy.sparse.linalg
from scipy.linalg import expm, sinm, cosm
import random

# Carleman input/output libraries
from carlin.io import get_Fj_from_model

# Toolbox for operations on polytopes
from polyhedron_tools.misc import polyhedron_to_Hrep, polyhedron_from_Hrep, chebyshev_center, radius, support_function
from polyhedron_tools.misc import BoxInfty

# Sage objects: Rings, Polynomials, Linear algebra
from sage.rings.all import RR, QQ
from sage.rings.real_double import RDF
from sage.rings.polynomial.polynomial_ring import polygens
#from sage.modules.free_module_element import vector
from sage.matrix.constructor import matrix, vector
from sage.modules.free_module_element import zero_vector

from sage.functions.other import real_part, imag_part, ceil, floor
from sage.functions.log import log, exp
from sage.symbolic.constants import pi

from sage.functions.trig import cos, sin

from sage.rings.infinity import Infinity    # oo

#from lib.norms import matrix_sup_norm

class NotImplementedException(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

def compute_flowpipe(A=None, X0=None, B=None, U=None, **kwargs):
    r"""Implements LGG reachability algorithm for the linear continuous system dx/dx = Ax + Bu.

    INPUTS:

    * ``A`` -- coefficient matrix of the system

    * ``X0`` -- initial set

    * ``B`` -- transformation of the input

    * ``U`` -- input set

    * ``time_step`` -- (default = 1e-2) time step

    * ``initial_time`` -- (default = 0) the initial time

    * ``time_horizon`` -- (default = 1) the final time

    * ``number_of_time_steps`` -- (default = ceil(T/tau)) number of time steps

    * "directions" -- (default: random, and a box) dictionary

    * ``solver`` -- LP solver. Valid options are:
        * 'GLPK' (default).
        * 'Gurobi'

    * ``base_ring`` -- base ring where polyhedral computations are performed
        Valid options are:
        * QQ - (default) rational field
        * RDF - real double field

    OUTPUTS:

    * ``flowpipe``

    """

    # ################
    # Parse input    #
    # ################
    if A is None:
        raise ValueError('System matrix A is missing.')
    else:
        if 'sage.matrix' in str(type(A)):
            n = A.ncols()
        elif type(A) == np.ndarray:
            n = A.shape[0]

    base_ring = kwargs['base_ring'] if 'base_ring' in kwargs else QQ

    if X0 is None:
        raise ValueError('Initial state X0 is missing.')
    elif 'sage.geometry.polyhedron' not in str(type(X0)) and type(X0) == list:
        # If X0 is not some type of polyhedron, set an initial point
        X0 = Polyhedron(vertices = [X0], base_ring = base_ring)
    elif 'sage.geometry.polyhedron' not in str(type(X0)) and X0.is_vector():
        X0 = Polyhedron(vertices = [X0], base_ring = base_ring)
    elif 'sage.geometry.polyhedron' in str(type(X0)):
        # ensure that all input sets are on the same ring
        # not sure about this
        if 1==0:
            if X0.base_ring() != base_ring:
                [F, g] = polyhedron_to_Hrep(X0)
                X0 = polyhedron_from_Hrep(F, g, base_ring=base_ring)
    else:
        raise ValueError('Initial state X0 not understood')

    if B is None:
        # the system is homogeneous: dx/dt = Ax
        got_homogeneous = True
    else:
        got_homogeneous = False
        if U is None:
            raise ValueError('Input range U is missing.')

    tau = kwargs['time_step'] if 'time_step' in kwargs else 1e-2

    t0 = kwargs['initial_time'] if 'initial_time' in kwargs else 0

    T = kwargs['time_horizon'] if 'time_horizon' in kwargs else 1

    global N
    N = kwargs['number_of_time_steps'] if 'number_of_time_steps' in kwargs else ceil(T/tau)

    directions = kwargs['directions'] if 'directions' in kwargs else {'select':'box'}

    global solver
    solver = kwargs['solver'] if 'solver' in kwargs else 'GLPK'

    global verbose
    verbose = kwargs['verbose'] if 'verbose' in kwargs else 0

    # this involves the convex hull of X0 and a Minkowski sum
    #first_element_evaluation = kwargs['first_element_evaluation'] if 'first_element_evaluation' in kwargs else 'approximate'

    # #######################################################
    # Generate template directions                          #
    # #######################################################
    if directions['select'] == 'box':

        if n==2:
            theta = [0,pi/2,pi,3*pi/2] # box
            dList = [vector(RR,[cos(t), sin(t)]) for t in theta]

        else: # directions of hypercube
            dList = []
            dList += [-identity_matrix(n).column(i) for i in range(n)]
            dList += [identity_matrix(n).column(i) for i in range(n)]

    elif directions['select'] == 'oct':

        if n != 2:
            raise NotImplementedError('Directions select octagon not implemented for n other than 2. Try box.')

        theta = [i*pi/4 for i in range(8)] # octagon
        dList = [vector(RR,[cos(t), sin(t)]) for t in theta]

    elif directions['select'] == 'random':

        order = directions['order'] if 'order' in directions else 12

        if n == 2:
            theta = [random.uniform(0, 2*pi.n(digits=5)) for i in range(order)]
            dList = [vector(RR,[cos(theta[i]), sin(theta[i])]) for i in range(order)]
        else:
            raise NotImplementedError('Directions select random not implemented for n greater than 2. Try box.')

    elif directions['select'] == 'custom':

        dList = directions['dList']

    else:

        raise TypeError('Template directions not understood.')


    # transform directions to numpy array, and get number of directions
    dArray = np.array(dList)
    k = len(dArray)

    global Phi_tau, expX0, alpha_tau_B

    if got_homogeneous: # dx/dx = Ax

        # #######################################################
        # Compute first element of the approximating sequence   #
        # #######################################################

        # compute matrix exponential exp(A*tau)
        Phi_tau = expm(np.multiply(A, tau))

        # compute exp(tau*A)X0
        expX0 = Phi_tau * X0

        # compute the bloating factor
        Ainfty = A.norm(Infinity)
        RX0 = radius(X0)

        unitBall = BoxInfty(center = zero_vector(n), radius = 1, base_ring = base_ring)
        alpha_tau = (exp(tau*Ainfty) - 1 - tau*Ainfty)*(RX0)
        alpha_tau_B = (alpha_tau*np.identity(n)) * unitBall

        # now we have that:
        # Omega0 = X0.convex_hull(expX0.Minkowski_sum(alpha_tau_B))

        # compute the first element of the approximating sequence, Omega_0
        #if first_element_evaluation == 'exact':
        #    Omega0 = X0.convex_hull(expX0.Minkowski_sum(alpha_tau_B))

        #elif first_element_evaluation == 'approximate': # NOT TESTED!!!
            #Omega0_A = dArray
        #    Omega0_b = np.zeros(k)

        #    for i, d in enumerate(dArray):
        # rho_X0_d = supp_fun_polyhedron(X0, d, solver=solver, verbose=verbose)
        #        rho_expX0_d = supp_fun_polyhedron(expX0, d, solver=solver, verbose=verbose)
        #        rho_alpha_tau_B_d = supp_fun_polyhedron(alpha_tau_B, d, solver=solver, verbose=verbose)
        #        Omega0_b[i] = max(rho_X0_d, rho_expX0_d + rho_alpha_tau_B_d);

        #    Omega0 = PolyhedronFromHSpaceRep(dArray, Omega0_b);

        #W_tau = Polyhedron(vertices = [], ambient_dim=n)
        # since W_tau = [], supp_fun_polyhedron returns 0

        # ################################################
        # Build the sequence of approximations Omega_i   #
        # ################################################

        Omega_i_Family_SF = [_Omega_i_supports_hom(d, X0) for d in dArray]


    else: # dx/dx = Ax + Bu

        global tau_V, beta_tau_B

        # compute range of the input under B, V = BU
        V = B * U

        # compute matrix exponential exp(A*tau)
        Phi_tau = expm(np.multiply(A, tau))

        # compute exp(tau*A)X0
        expX0 = Phi_tau * X0

        # compute the initial over-approximation
        tau_V = (tau*np.identity(n)) * V

        # compute the bloating factor
        Ainfty = A.norm(Infinity)
        RX0 = radius(X0)
        RV = radius(V)

        unitBall = BoxInfty(center = zero_vector(n), radius = 1, base_ring = base_ring)
        alpha_tau = (exp(tau*Ainfty) - 1 - tau*Ainfty)*(RX0 + RV/Ainfty)
        alpha_tau_B = (alpha_tau*np.identity(n)) * unitBall

        # compute the first element of the approximating sequence, Omega_0
        #aux = expX0.Minkowski_sum(tau_V)
        #Omega0 = X0.convex_hull(aux.Minkowski_sum(alpha_tau_B))

        beta_tau = (exp(tau*Ainfty) - 1 - tau*Ainfty)*(RV/Ainfty)
        beta_tau_B = (beta_tau*np.identity(n)) * unitBall

        #W_tau = tau_V.Minkowski_sum(beta_tau_B)

        # ################################################
        # Build the sequence of approximations Omega_i   #
        # ################################################

        Omega_i_Family_SF = [_Omega_i_supports_inhom(d, X0) for d in dArray]


    # ################################################
    # Build the approximating polyhedra              #
    # ################################################

    # each polytope is built using the support functions over-approximation
    Omega_i_Poly = list()

    # This loop can be vectorized (?)
    for i in range(N):    # we have N polytopes

        # for each one, use all directions
        A = matrix(base_ring, k, n);
        b = vector(base_ring, k)

        for j in range(k): #run over directions
            s_fun = Omega_i_Family_SF[j][i]
            A.set_row(j, dList[j])
            b[j] = s_fun

        Omega_i_Poly.append( polyhedron_from_Hrep(A, b, base_ring = base_ring) )

    return Omega_i_Poly


def _Omega_i_supports_hom(d, X0):
    r"""Receives a direction d, and outputs the support function
    rho_i of Omega_i at d"""

    r = []
    s = []
    rhoi = []

    r.append(d)
    s.append(0)

    # append to rhoi the support function of Omega0 at d
    rho_X0_d = support_function(X0, d, solver=solver, verbose=verbose)
    rho_expX0_d = support_function(expX0, d, solver=solver, verbose=verbose)
    rho_alpha_tau_B_d = support_function(alpha_tau_B, d, solver=solver, verbose=verbose)
    rhoi.append(max(rho_X0_d, rho_expX0_d + rho_alpha_tau_B_d))

    for i in [0..N-2]:

        r.append(np.dot(Phi_tau.transpose(),r[i]))
        s.append(s[i])

        # append to rhoi the support function of Omega0 at r[i+1]
        rho_X0_rip1 = support_function(X0, r[i+1], solver=solver, verbose=verbose)
        rho_expX0_rip1 = support_function(expX0, r[i+1], solver=solver, verbose=verbose)
        rho_alpha_tau_B_rip1 = support_function(alpha_tau_B, r[i+1], solver=solver, verbose=verbose)
        rhoi.append(s[i+1] + max(rho_X0_rip1, rho_expX0_rip1 + rho_alpha_tau_B_rip1))

        #rhoi.append(s[i+1] + support_function(Omega0, r[i+1], solver=solver, verbose=verbose))


    return rhoi


def _Omega_i_supports_inhom(d, X0):
    r"""Receives a direction d, and outputs the support function
    rho_i of Omega_i at d"""

    r = []
    s = []
    rhoi = []

    r.append(d)
    s.append(0)

    # append to rhoi the support function of Omega0 at d
    rho_X0_d = support_function(X0, d, solver=solver, verbose=verbose)
    rho_expX0_d = support_function(expX0, d, solver=solver, verbose=verbose)
    rho_alpha_tau_B_d = support_function(alpha_tau_B, d, solver=solver, verbose=verbose)
    rhoi.append(max(rho_X0_d, rho_expX0_d + rho_alpha_tau_B_d))

    for i in [0..N-2]:

        r.append(np.dot(Phi_tau.transpose(),r[i]))

        #recall that:
        #W_tau = tau_V.Minkowski_sum(beta_tau_B)
        rho_tau_V_ri = support_function(tau_V, r[i], solver=solver, verbose=verbose);
        rho_beta_tau_B_ri = support_function(beta_tau_B, r[i], solver=solver, verbose=verbose);
        s.append(s[i] + rho_tau_V_ri + rho_beta_tau_B_ri)

        # append to rhoi the support function of Omega0 at r[i+1]
        rho_X0_rip1 = support_function(X0, r[i+1], solver=solver, verbose=verbose)
        rho_expX0_rip1 = support_function(expX0, r[i+1], solver=solver, verbose=verbose)
        rho_alpha_tau_B_rip1 = support_function(alpha_tau_B, r[i+1], solver=solver, verbose=verbose)
        rhoi.append(s[i+1] + max(rho_X0_rip1, rho_expX0_rip1 + rho_alpha_tau_B_rip1))

        #rhoi.append(s[i+1] + support_function(Omega0, r[i+1], solver=solver, verbose=verbose))

    return rhoi


def plot_flowpipe(fp, **kwargs):
    # TO-DO : this projection does not return an actual Polyhedron.
    # Hence, the graphics cannot be displayed and modified in the same way
    # as in 2D. Is there a way to obtain a polyhedron?
    # (this use-case was also raised by Alexey).

    from sage.geometry.polyhedron.plot import Projection

    n = fp[0].ambient_dim()

    if n == 2:

        # plot the result
        myFig = Graphics()
        myFig = sum(p.plot(alpha=0.5) for p in fp)


    elif n>2:

        if 'directions' in kwargs:
            v = kwargs['directions']
        else:
            print 'WARNING: projection directions not specified. Assuming directions=[0,1]'
            v = [0,1];

        fp_proj = [Projection(p, proj = lambda x : [ x[v[0]], x[v[1]] ]) for p in fp]

        # plot the result
        myFig = Graphics()
        myFig = sum(p.plot() for p in fp_proj)
        #myFig.show()

    return myFig
