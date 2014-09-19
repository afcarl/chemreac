#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, division

import argh
import numpy as np

from chemreac import (
    ReactionDiffusion, FLAT, SPHERICAL,
    CYLINDRICAL, BANDED, Geom_names
)
from chemreac.integrate import run
from chemreac.util.plotting import plot_C_vs_t_and_x

"""
Demo of diffusion.
"""

# <geometric_diffusion.png>

GEOMS = (FLAT, SPHERICAL, CYLINDRICAL)


def main(tend=10.0, N=25, nt=30, nstencil=3, linterpol=False,
         rinterpol=False, num_jacobian=False, no_plots=False):
    x = np.linspace(0.1, 1.0, N+1)
    f = lambda x: 2*x**2/(x**4+1)  # f(0)=0, f(1)=1, f'(0)=0, f'(1)=0
    y0 = f(x[1:])+x[0]  # (x[0]/2+x[1:])**2

    t0 = 1e-10
    tout = np.linspace(t0, tend, nt)

    fig = plt.figure()
    res, systems = [], []
    for G in GEOMS:
        sys = ReactionDiffusion(1, [], [], [], N=N, D=[0.02], x=x,
                                geom=G, nstencil=nstencil, lrefl=not linterpol,
                                rrefl=not rinterpol)
        yout, info = run(sys, y0, tout, with_jacobian=(not num_jacobian))
        res.append(yout)
        systems.append(sys)

    if not no_plots:
        # matplotlib
        from mpl_toolkits.mplot3d import Axes3D
        import matplotlib
        from matplotlib import cm
        from matplotlib import pyplot as plt

        # Plot spatio-temporal conc. evolution
        for i, G in enumerate(GEOMS):
            yout = res[i]
            ax = fig.add_subplot(2, 3, G+1, projection='3d')

            plot_C_vs_t_and_x(sys, tout, yout[:, :, 0], 0, ax,
                              rstride=1, cstride=1, cmap=cm.gist_earth)
            ax.set_title(Geom_names[G])

        # Plot mass conservation
        ax = fig.add_subplot(2, 3, 4)
        for j in range(3):
            ax.plot(tout, np.apply_along_axis(
                systems[j].integrated_conc, 1, res[j][:, :, 0]), label=str(j))
        ax.legend(loc='best')
        ax.set_title('Mass conservation')

        # Plot difference from flat evolution (not too informative..)
        for i, G in enumerate(GEOMS):
            yout = res[i][:, :, 0]  # only one specie
            if i != 0:
                yout = yout - res[0][:, :, 0]  # difference (1 specie)
                ax = fig.add_subplot(2, 3, 3+G+1, projection='3d')

                plot_C_vs_t_and_x(sys, tout, yout[:, :], 0, ax,
                                  rstride=1, cstride=1, cmap=cm.gist_earth)
                ax.set_title(Geom_names[G] + ' minus ' + Geom_names[0])

        plt.show()


if __name__ == '__main__':
    argh.dispatch_command(main)