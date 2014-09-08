# -*- coding: utf-8 -*-

"""
Functions to analyze output.
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *

import numpy as np


def solver_linear_error(y, rtol, atol, logy=False, scale_err=1.0):
    """
    Returns linear estimated error bounds from numerical integration

    Parameters
    ==========
    y : array_like
         Output from integration (before back-transformation is applied)
    rtol : float
         Relative tolerance
    atol : float
         Absolute tolerance
    logy : bool
         Is y from a run with logarithmic concentration?
    scale_err : float
         scale estimated error bounds (useful for testing)

    Returns
    =======
    Length 2 tuple of arrays corrsponding to lower and upper bounds around y.

    Notes
    =====
    Assumes maximum mangitude of error be: e_max = \|y*rtol\| + atol
    """
    solver_err = scale_err*(np.abs(y*rtol) + atol)
    if logy:
        res = np.exp(y - solver_err), np.exp(y + solver_err)
    else:
        res = y - solver_err, y + solver_err
    return np.array(res)


def suggest_t0(rd, y0, max_f=1.0):
    """
    Suggests an appropriate initial time,
    useful when logy==True and logt==True,
    If suggested t0 > 1, 1 is returned.

    Parameters
    ==========
    rd: ReactionDiffusion instance
         System at hand
    y0: sequence
         initial concentrations
    max_f: float
         upper bound of absolute value for largest element in for the
         inital step.
    """
    fout = rd.alloc_fout()
    rd.f(0, y0, fout)
    fout_maxabs = np.max(np.abs(fout))
    if fout_maxabs < max_f:
        return 1.0
    else:
        return max_f/fout_maxabs
