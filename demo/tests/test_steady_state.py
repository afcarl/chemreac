# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import, unicode_literals

from itertools import product

import numpy as np
import pytest

from steady_state import integrate_rd

TR_FLS = (True, False)

@pytest.mark.parametrize('params', list(product(TR_FLS, TR_FLS, TR_FLS, TR_FLS, TR_FLS, [3], [1e-7])))
def test_steady_state(params):
    ly, lt, r, lr, rr, ns, forgiveness = params
    # notice forgiveness << 1
    # this is because static conditions is very simple to integrate
    atol = 1e-6
    res = integrate_rd(geom='f', logt=lt, logy=ly, N=128, random=r, nstencil=ns,
                       lrefl=lr, rrefl=rr, atol=atol, rtol=1e-6)
    for ave_rmsd_over_atol in res[3]:
        assert np.all(ave_rmsd_over_atol < forgiveness)

@pytest.mark.parametrize('params', list(product(TR_FLS, TR_FLS, TR_FLS, [5, 7])))
def test_steady_state__high_stencil(params):
    ly, lt, r, nstencil = params
    test_steady_state((ly, lt, r, False, False, nstencil, 1e-4))

@pytest.mark.xfail
@pytest.mark.parametrize('params', list(product(TR_FLS, TR_FLS, TR_FLS, 'cs')))
def test_steady_state__curved_geom(params):
    ly, lt, r, geom = params
    atol = 1e-6
    res = integrate_rd(geom=geom, logt=lt, logy=ly, N=128, random=r,
                       lrefl=True, rrefl=True, atol=atol, rtol=1e-6)
    for ave_rmsd_over_atol in res[3]:
        assert np.all(ave_rmsd_over_atol < 1.0)