#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import

from math import log

import argh
import numpy as np

from chemreac import (
    ReactionDiffusion, FLAT, CYLINDRICAL, SPHERICAL, Geom_names
)
from chemreac.integrate import run


def gaussian(x, mu, sigma, logy, logx):
    x = np.exp(x) if logx else x
    a = 1/sigma/(2*np.pi)**0.5
    b = -0.5*((x-mu)/sigma)**2
    if logy:
        return log(a) + b
    else:
        return a*np.exp(b)


def integrate_rd(D=2e-4, t0=3., tend=7., x0=0.1, xend=1.0, N=128, offset=0.01,
                 mobility=1e-6, nt=25, geom='f', logt=False, logy=False,
                 logx=False, random=False, nstencil=3, lrefl=False,
                 rrefl=False, num_jacobian=False, method='bdf', plot=False,
                 atol=1e-6, rtol=1e-6, random_seed=42, surf_chg=0.0,
                 sigma_q=23):
    if random_seed:
        np.random.seed(random_seed)
    n = 2
    tout = np.linspace(t0, tend, nt)
    geom = {'f': FLAT, 'c': CYLINDRICAL, 's': SPHERICAL}[geom]

    # Setup the grid
    _x0 = log(x0) if logx else x0
    _xend = log(xend) if logx else xend
    x = np.linspace(_x0, _xend, N+1)
    if random:
        x += (np.random.random(N+1)-0.5)*(_xend-_x0)/(N+2)

    # Setup the system
    stoich_reac = []
    stoich_prod = []
    k = []
    bin_k_factor = [[] for _ in range(N)]
    bin_k_factor_span = []

    sys = ReactionDiffusion(
        n, stoich_reac, stoich_prod, k, N,
        D=[D, D],
        z_chg=[1, -1],
        mobility=[mobility, -mobility],
        x=x,
        bin_k_factor=bin_k_factor,
        bin_k_factor_span=bin_k_factor_span,
        geom=geom,
        logy=logy,
        logt=logt,
        logx=logx,
        nstencil=nstencil,
        lrefl=lrefl,
        rrefl=rrefl,
        auto_efield=True,
        surf_chg=surf_chg,
        eps=80.10,  # water at 20 deg C
    )

    # Initial conditions
    sigma = (xend-x0)/sigma_q
    y0 = 0.13*np.vstack((
        gaussian(sys.xcenters, x0+(0.5+offset)*(xend-x0), sigma, logy, logx),
        gaussian(sys.xcenters, x0+(0.5-offset)*(xend-x0), sigma, logy, logx)
    )).transpose()

    if plot:
        # Plot initial E-field
        import matplotlib.pyplot as plt
        sys.calc_efield(y0.flatten())
        plt.subplot(3, 1, 3)
        plt.plot(sys.xcenters, sys.efield, label="E at t=t0")
        plt.plot(sys.xcenters, sys.xcenters*0, label="0")
    # Run the integration
    t = np.log(tout) if logt else tout
    yout, info = run(sys, y0.flatten(), t,
                     atol=atol, rtol=rtol,
                     with_jacobian=(not num_jacobian), method=method)
    yout = np.exp(yout) if logy else yout

    # Plot results
    if plot:
        def _plot(y, ttl=None, apply_exp_on_y=False, **kwargs):
            plt.plot(sys.xcenters, np.exp(y) if apply_exp_on_y else y,
                     **kwargs)
            if N < 100:
                plt.vlines(sys.x, 0, np.ones_like(sys.x)*max(y), linewidth=.1,
                           colors='gray')
            plt.xlabel('x / m')
            plt.ylabel('C / M')
            if ttl:
                plt.title(ttl)

        for i in range(nt):
            plt.subplot(3, 1, 1)
            c = 1-tout[i]/tend
            c = (1.0-c, .5-c/2, .5-c/2)
            _plot(yout[i, :, 0], 'Simulation (N={})'.format(sys.N),
                  apply_exp_on_y=logy, c=c, label='$z_A=1$' if i==0 else None)
            _plot(yout[i, :, 1], apply_exp_on_y=logy, c=c[::-1],
                  label='$z_B=-1$' if i==0 else None)
            plt.legend()

            plt.subplot(3, 1, 2)
            if logy:
                delta_y = np.exp(yout[i, :, 0]) - np.exp(yout[i, :, 1])
            else:
                delta_y = yout[i, :, 0] - yout[i, :, 1]
            _plot(delta_y, 'Diff'.format(sys.N),
                  apply_exp_on_y=logy,
                  c=[c[2], c[0], c[1]],
                  label='A-B (positive excess)' if i==0 else None)
            plt.legend()
            plt.xlabel('Time / s')
            plt.ylabel(r'C')
        plt.subplot(3, 1, 3)
        plt.plot(sys.xcenters, sys.efield, label="E at t=tend")
        plt.xlabel("$x / m$")
        plt.ylabel("$E / V\cdot m^{-1}$")
        plt.legend()
        plt.tight_layout()
        plt.show()
    return tout, yout, info, sys

if __name__ == '__main__':
    argh.dispatch_command(integrate_rd)
