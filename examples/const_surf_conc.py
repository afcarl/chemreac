#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Diffusion from constant concentration surface
---------------------------------------------

:download:`examples/const_surf_conc.py` models a diffusion process
and reports the error from the model integration by comparison to the
analytic solution (intial concentrations are taken from Green's
function expressions for respective geometry).

::

 $ python const_surf_conc.py --help

.. exec::
   echo "::\\n\\n"
   python examples/examples/const_surf_conc.py --help | sed "s/^/   /"

Here is an example generated by:

::

 $ python const_surf_conc.py --plot --savefig const_surf_conc.png

.. image:: ../_generated/const_surf_conc.png

Solving the transformed system (:math:`\\frac{d}{dt} \\ln(c(\\ln(x), t))`):

::

 $ python const_surf_conc.py --logx --logy --x0 1e-6 --scaling 1e-20\
 --factor 1e12 --plot --savefig const_surf_conc_logy_logx.png

.. image:: ../_generated/const_surf_conc_logy_logx.png


note the much better performance of this transformed (and scaled) system
compared to the untransformed one.

"""

from __future__ import absolute_import, division, print_function

from collections import defaultdict

import argh
import numpy as np

from chemreac import ReactionDiffusion
from chemreac.integrate import Integration
from chemreac.util.grid import generate_grid
from chemreac.util.plotting import save_and_or_show_plot
from chemreac.util.testing import spat_ave_rmsd_vs_time


def analytic(x, t, D, x0, xend, logx=False, c_s=1):
    r"""
    Evaluates the analytic expression for the concentration
    in a medium with a constant source term at x=0:

    .. math ::

        c(x, t) = c_s \mathrm{erfc}\left( \frac{x}{2\sqrt{Dt}}\right)

    where :math:`c_s` is the constant surface concentration.
    """
    import scipy.special
    if t.ndim == 1:
        t = t.reshape((t.size, 1))
    x = np.exp(x) if logx else x
    return c_s * scipy.special.erfc(x/(2*(D*t)**0.5))


def integrate_rd(D=2e-3, t0=1., tend=13., x0=1e-10, xend=1.0, N=256,
                 nt=42, logt=False, logy=False, logx=False,
                 random=False, k=1.0, nstencil=3, linterpol=False,
                 rinterpol=False, num_jacobian=False, method='bdf',
                 integrator='scipy', iter_type='default',
                 linear_solver='default', atol=1e-8, rtol=1e-10, factor=1e5,
                 random_seed=42, plot=False, savefig='None', verbose=False,
                 scaling=1.0, ilu_limit=1000.0, first_step=0.0, n_jac_diags=0):
    """
    Solves the time evolution of diffusion from a constant (undepletable)
    source term. Optionally plots the results. In the plots time is represented
    by color scaling from black (:math:`t_0`) to red (:math:`t_{end}`)
    """
    if t0 == 0.0:
        raise ValueError("t0==0 => Dirac delta function C0 profile.")
    if random_seed:
        np.random.seed(random_seed)
    tout = np.linspace(t0, tend, nt)

    units = defaultdict(lambda: 1)
    units['amount'] = 1.0/scaling

    # Setup the grid
    x = generate_grid(x0, xend, N, logx, random=random)
    modulation = [1 if (i == 0) else 0 for i in range(N)]

    rd = ReactionDiffusion.nondimensionalisation(
        2,
        [[0], [1]],
        [[1], [0]],
        [k, factor*k],
        N=N,
        D=[0, D],
        x=x,
        logy=logy,
        logt=logt,
        logx=logx,
        nstencil=nstencil,
        lrefl=not linterpol,
        rrefl=not rinterpol,
        modulated_rxns=[0, 1],
        modulation=[modulation, modulation],
        unit_registry=units,
        ilu_limit=ilu_limit,
        n_jac_diags=n_jac_diags,
        faraday_const=1,
        vacuum_permittivity=1,
    )

    # Calc initial conditions / analytic reference values
    Cref = analytic(rd.xcenters, tout, D, x0, xend, logx).reshape(
        nt, N, 1)
    source = np.zeros_like(Cref[0, ...])
    source[0, 0] = factor
    y0 = np.concatenate((source, Cref[0, ...]), axis=1)

    # Run the integration
    integr = Integration.nondimensionalisation(
        rd, y0, tout, integrator=integrator, atol=atol, rtol=rtol,
        with_jacobian=(not num_jacobian), method=method,
        iter_type=iter_type,
        linear_solver=linear_solver, first_step=first_step)
    Cout = integr.get_with_units('Cout')
    if verbose:
        import pprint
        pprint.pprint(integr.info)
    spat_ave_rmsd_over_atol = spat_ave_rmsd_vs_time(
        Cout[:, :, 1], Cref[:, :, 0]) / atol
    tot_ave_rmsd_over_atol = np.average(spat_ave_rmsd_over_atol)

    if plot:
        # Plot results
        import matplotlib.pyplot as plt
        plt.figure(figsize=(6, 10))

        def _plot(C, c, ttl=None, vlines=False,
                  smooth=True):
            if vlines:
                plt.vlines(rd.x, 0, np.ones_like(rd.x)*max(C),
                           linewidth=1, colors='gray')
            if smooth:
                plt.plot(rd.xcenters, C, c=c)
            else:
                for i, _C in enumerate(C):
                    plt.plot([rd.x[i], rd.x[i+1]], [_C, _C], c=c)

            plt.xlabel('x / m')
            plt.ylabel('C / M')
            if ttl:
                plt.title(ttl)

        for i in range(nt):
            kwargs = dict(smooth=(N >= 20),
                          vlines=(i == 0 and N < 20))

            c = 1-tout[i]/tend
            c = (1.0-c, .5-c/2, .5-c/2)
            plt.subplot(4, 1, 1)
            _plot(Cout[i, :, 1], c, 'Simulation (N={})'.format(rd.N),
                  **kwargs)

            plt.subplot(4, 1, 2)
            _plot(Cref[i, :, 0], c, 'Analytic', **kwargs)

            plt.subplot(4, 1, 3)
            _plot((Cout[i, :, 1]-Cref[i, :, 0]), c,
                  "Error".format(atol),
                  **kwargs)

            plt.subplot(4, 1, 4)
            plt.plot(integr.tout, spat_ave_rmsd_over_atol)
            plt.plot([integr.tout[0], integr.tout[-1]],
                     [tot_ave_rmsd_over_atol]*2, '--')
            plt.title("RMSD / atol")

        plt.tight_layout()
        save_and_or_show_plot(savefig=savefig)

    return tout, Cout, integr.info, rd, tot_ave_rmsd_over_atol


if __name__ == '__main__':
    argh.dispatch_command(integrate_rd, output_file=None)
