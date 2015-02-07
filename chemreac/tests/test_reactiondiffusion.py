# -*- coding: utf-8 -*-

from __future__ import division, print_function

from itertools import product
import os

import numpy as np
import pytest

from chemreac import ReactionDiffusion, FLAT, SPHERICAL, CYLINDRICAL
from chemreac.symbolic import SymRD
from chemreac.util.banded import get_banded
from chemreac.util.compressed_jac_store import get_compressed
from chemreac.util.grid import padded_centers, stencil_pxci_lbounds, pxci_to_bi
from chemreac.util.testing import slow

TR_FLS = [True, False]
TRUE_FALSE_PAIRS = list(product(TR_FLS, TR_FLS))


def _test_f(rd, t, y, fref=None):
    fout = rd.alloc_fout()
    rd.f(t, np.asarray(y, dtype=np.float64), fout)
    if fref is None:
        fref = fout
    else:
        assert np.allclose(fout, fref)
        if isinstance(rd, SymRD):
            return
    _test_f(SymRD.from_rd(rd), t, y, fref)


def _test_dense_jac_rmaj(rd, t, y, jref=None):
    jout = rd.alloc_jout(banded=False)
    rd.dense_jac_rmaj(t, np.asarray(y, dtype=np.float64), jout)
    atol = 1e-13
    rtol = 1e-13
    if jref is None:
        jref = jout
    else:
        # Not perfect Jacobian
        # only nearest neighbour
        # assert np.allclose(jout, jref)
        # ...hence:
        for ri in range(rd.ny):
            for ci in range(max(0, ri-rd.n), min(rd.ny, ri+rd.n+1)):
                out, ref = jout[ri, ci], jref[ri, ci]
                assert abs(out - ref) < atol + rtol*abs(ref)
        if isinstance(rd, SymRD):
            return
    _test_dense_jac_rmaj(SymRD.from_rd(rd), t, y, jref)


def _test_f_and_dense_jac_rmaj(rd, t, y, fref=None, jref=None):
    _test_f(rd, t, y, fref)
    _test_dense_jac_rmaj(rd, t, y, jref)


def test_autobinary():
    from chemreac.chemistry import (
        Reaction, ReactionSystem, mk_sn_dict_from_names
    )
    sbstncs = mk_sn_dict_from_names('AB')
    k = 3.0
    r1 = Reaction({'A': 2}, {'B': 1}, k=k)
    rsys = ReactionSystem([r1])
    rd = rsys.to_ReactionDiffusion(sbstncs)

    _test_f_and_dense_jac_rmaj(rd, 0, [1, 37], [-2*3, 3])


def test_ReactionDiffusion__f__wrong_fout_dimension():
    y0 = np.array([2.0, 3.0])
    k = 5.0
    # A -> B
    rd = ReactionDiffusion(2, [[0]], [[1]], [k])
    fout = np.ones((1,))*99  # fout too small
    with pytest.raises(AssertionError):
        rd.f(0.0, y0, fout)


def test_ReactionDiffusion__too_few_species():
    # Ensure exception raised when referencing species indices > (n-1)
    # A -> B
    n = 1  # wrong: A, B makes 2
    with pytest.raises(RuntimeError):
        ReactionDiffusion(n, [[0]], [[1]], [5.0])


@pytest.mark.parametrize("N", [1, 3, 4])
def test_ReactionDiffusion__only_1_reaction(N):
    t0 = 3.0
    y0 = np.array([2.0, 3.0]*N)
    k = 5.0
    # A -> B
    rd = ReactionDiffusion(2, [[0]], [[1]], [k], N, D=[0.0, 0.0])
    fref = np.array([-10.0, 10.0]*N)
    _test_f(rd, t0, y0, fref)

    jref = np.zeros((2*N, 2*N))
    for i in range(N):
        jref[i*2,   i*2] = -k
        jref[i*2+1, i*2] = k
    _test_dense_jac_rmaj(rd, t0, y0, jref)


def test_ReactionDiffusion__actv_1():
    y0 = np.array([2.0, 3.0, 7.0])
    k = 5.0
    # A + C -(+A)-> B + C
    rd = ReactionDiffusion(3, [[0, 0, 2]], [[1, 2]], [k], stoich_actv=[[0, 2]])
    r = k*y0[0]*y0[2]
    _test_f_and_dense_jac_rmaj(rd, 0, y0, [-2*r, r, 0])


def test_ReactionDiffusion__actv_2():
    y0 = np.array([2.0, 3.0, 9.0])
    k = 5.0
    # A + C --(+A+5*C)--> B
    rd = ReactionDiffusion(3, [[0, 0, 2, 2, 2, 2, 2, 2]], [[1]], [k],
                           stoich_actv=[[0, 2]])
    r = k*y0[0]*y0[2]
    _test_f_and_dense_jac_rmaj(rd, 0, y0, [-2*r, r, -6*r])


@pytest.mark.parametrize("log", TRUE_FALSE_PAIRS)
def test_ReactionDiffusion__lrefl_3(log):
    # Diffusion without reaction
    # 3 bins
    t0 = 3.0
    logy, logt = log
    D = 17.0
    y0 = np.array([23.0, 27.0, 37.0])
    x = [5.0, 9.0, 13.0, 15.0]
    nstencil = 3
    xc = [3.0, 7.0, 11.0, 14.0, 16.0]

    rd = ReactionDiffusion(1, [], [], [], D=[D], x=x, logy=logy,
                           nstencil=nstencil, logt=logt,
                           lrefl=True, rrefl=False)
    assert np.allclose(rd._xc, xc)

    # In [7]: xlst=[0, 3, 7, 11, 14]
    # In [8]: print(finite_diff_weights(2, xlst[1:4], x0=xlst[2])[-1][-1])
    # [1/16, -1/8, 1/16]
    # In [9]: print(finite_diff_weights(2, xlst[2:5], x0=xlst[3])[-1][-1])
    # [1/14, -1/6, 2/21]
    # In [10]: print(finite_diff_weights(2, xlst[2:5], x0=xlst[4])[-1][-1])
    # [1/14, -1/6, 2/21]

    D_weight_ref = np.array([1/16, -1/8, 1/16, 1/14, -1/6,
                             2/21, 1/14, -1/6, 2/21])
    assert np.allclose(rd.D_weight, D_weight_ref)

    fref = np.array([
        1/16*y0[0] - 1/8*y0[0] + 1/16*y0[1],  # lrefl=True
        1/14*y0[0] - 1/6*y0[1] + 2/21*y0[2],
        1/14*y0[0] - 1/6*y0[1] + 2/21*y0[2],  # rrefl=False
    ])*D

    if logy:
        fref /= y0
    if logt:
        fref *= t0

    y = np.log(y0) if logy else y0
    t = np.log(t0) if logt else t0
    _test_f(rd, t, y, fref)

    if logy:
        jref = D*np.array([
            [
                -1/16*y0[1]/y0[0],
                1/16*y0[1]/y0[0],
                0
            ],
            [
                1/14*y0[0]/y0[1],
                -1/14*y0[0]/y0[1] - 2/21*y0[2]/y0[1],
                2/21*y0[2]/y0[1]
            ],
            [
                1/14*y0[0]/y0[2],
                -1/6*y0[1]/y0[2],
                -1/14*y0[0]/y0[2] + 1/6*y0[1]/y0[2]
            ]
        ])
    else:
        jref = D*np.array([
            [1/16-1/8, 1/16, 0],
            [1/14, -1/6, 2/21],
            [1/14, -1/6, 2/21],
        ])

    if logt:
        jref *= t0

    y = np.log(y0) if logy else y0
    t = np.log(t0) if logt else t0
    _test_dense_jac_rmaj(rd, t, y, jref)


@pytest.mark.parametrize("log", TRUE_FALSE_PAIRS)
def test_ReactionDiffusion__rrefl_3(log):
    # Diffusion without reaction
    # 3 bins
    t0 = 3.0
    logy, logt = log
    D = 17.0
    y0 = np.array([23.0, 27.0, 37.0])
    x = [5.0, 9.0, 13.0, 15.0]
    nstencil = 3
    xc = [3.0, 7.0, 11.0, 14.0, 16.0]

    rd = ReactionDiffusion(1, [], [], [], D=[D], x=x, logy=logy,
                           nstencil=nstencil, logt=logt,
                           lrefl=False, rrefl=True)
    assert np.allclose(rd._xc, xc)

    # In [7]: xlst=[3, 7, 11, 14, 16]
    # In [8]: print(finite_diff_weights(2, xlst[1:4], x0=xlst[1])[-1][-1])
    # [1/14, -1/6, 2/21]
    # In [9]: print(finite_diff_weights(2, xlst[1:4], x0=xlst[2])[-1][-1])
    # [1/14, -1/6, 2/21]
    # In [10]: print(finite_diff_weights(2, xlst[2:5], x0=xlst[3])[-1][-1])
    # [2/15, -1/3, 1/5]
    D_weight_ref = np.array([1/14, -1/6, 2/21, 1/14,
                             -1/6, 2/21, 2/15, -1/3, 1/5])
    assert np.allclose(rd.D_weight, D_weight_ref)

    fref = np.array([
        1/14*y0[0] - 1/6*y0[1] + 2/21*y0[2],  # lrefl=False
        1/14*y0[0] - 1/6*y0[1] + 2/21*y0[2],
        2/15*y0[1] - 1/3*y0[2] + 1/5*y0[2],  # rrefl=True
    ])*D

    if logy:
        fref /= y0
    if logt:
        fref *= t0

    y = np.log(y0) if logy else y0
    t = np.log(t0) if logt else t0
    _test_f(rd, t, y, fref)

    if logy:
        jref = D*np.array([
            [
                1/6*y0[1]/y0[0] - 2/21*y0[2]/y0[0],
                -1/6*y0[1]/y0[0],
                2/21*y0[2]/y0[0]
            ],
            [
                1/14*y0[0]/y0[1],
                -1/14*y0[0]/y0[1] - 2/21*y0[2]/y0[1],
                2/21*y0[2]/y0[1]
            ],
            [
                0,
                2/15*y0[1]/y0[2],
                -2/15*y0[1]/y0[2]
            ]
        ])
    else:
        jref = D*np.array([
            [1/14, -1/6, 2/21],
            [1/14, -1/6, 2/21],
            [0,    2/15, 1/5-1/3]
        ])

    if logt:
        jref *= t0

    _test_dense_jac_rmaj(rd, t, y, jref)


@slow
@pytest.mark.parametrize("log", TRUE_FALSE_PAIRS)
def test_ReactionDiffusion__lrefl_7(log):
    # Diffusion without reaction (7 bins)
    from sympy import finite_diff_weights
    lrefl, rrefl = True, False
    N = 7
    t0 = 3.0
    logy, logt = log
    D = 17.0
    nstencil = 5
    nsidep = (nstencil-1)//2
    x = np.array([3, 5, 13, 17, 23, 25, 35, 37], dtype=np.float64)
    y0 = np.array([12, 8, 11, 5, 7, 4, 9], dtype=np.float64)
    xc_ = padded_centers(x, nsidep)
    lb = stencil_pxci_lbounds(nstencil, N, lrefl=lrefl, rrefl=rrefl)

    rd = ReactionDiffusion(1, [], [], [], D=[D], x=x, logy=logy,
                           logt=logt, N=N, nstencil=nstencil,
                           lrefl=lrefl, rrefl=rrefl)

    y = np.log(y0) if logy else y0
    t = np.log(t0) if logt else t0
    le = nsidep if lrefl else 0
    D_weight_ref = np.array([
        finite_diff_weights(
            2, xc_[lb[i]:lb[i]+nstencil], x0=xc_[le+i])[-1][-1]
        for i in range(N)], dtype=np.float64)
    assert np.allclose(rd.D_weight, D_weight_ref.flatten())

    yi = pxci_to_bi(nstencil, N)

    fref = D*np.array([
        sum([rd.D_weight[i*nstencil+j]*y0[yi[lb[i]+j]]
             for j in range(nstencil)])
        for i in range(N)
    ])

    if logy:
        fref /= y0
    if logt:
        fref *= t0

    _test_f(rd, t, y, fref)

    if logy:
        def cb(i, j):
            if abs(i-j) > 1:
                return 0  # imperfect Jacobian
            elif i == j:
                res = 0
                for k in range(nstencil):
                    cyi = yi[lb[i] + k]  # current y index
                    if cyi != i:
                        res -= y0[cyi]/y0[i]*rd.D_weight[i*nstencil + k]
                return res
            else:
                res = 0
                for k in range(nstencil):
                    cyi = yi[lb[i] + k]  # current y index
                    if cyi == j:
                        res += y0[j]/y0[i]*rd.D_weight[i*nstencil + k]
                return res
    else:
        def cb(i, j):
            if abs(i-j) > 1:
                return 0  # imperfect Jacobian
            res = 0
            for k in range(nstencil):
                if yi[lb[i]+k] == j:
                    res += rd.D_weight[i*nstencil + k]
            return res
    jref = D*np.array([cb(i, j) for i, j in product(
        range(N), range(N))]).reshape(N, N)
    if logt:
        jref *= t0

    _test_dense_jac_rmaj(rd, t, y, jref)


@pytest.mark.parametrize("N", [1, 3, 4, 5])
def test_ReactionDiffusion__only_1_reaction__logy(N):
    # See <test_ReactionDiffusion__only_1_reaction__logy.png>
    t0 = 3.0
    y0 = np.array([2.0, 3.0]*N)
    k = 5.0
    # A -> B
    rd = ReactionDiffusion(2, [[0]], [[1]], [k], N, D=[0.0, 0.0], logy=True)
    fref = np.array([(-k, k*y0[i*2]/y0[i*2+1]) for i in range(N)]).flatten()
    _test_f(rd, t0, np.log(y0), fref)

    jref = np.zeros((2*N, 2*N))
    for i in range(N):
        A = y0[i*2]
        B = y0[i*2+1]
        jref[i*2+1, i*2] = k/B*A
        jref[i*2+1, i*2+1] = -k/B*A
    _test_dense_jac_rmaj(rd, t0, np.log(y0), jref)


@pytest.mark.parametrize("N", [1, 3, 4, 5])
def test_ReactionDiffusion__only_1_reaction__logy__logt(N):
    # See <test_ReactionDiffusion__only_1_reaction__logy_logt.png>
    t0 = 3.0
    y0 = np.array([2.0, 3.0]*N)
    k = 5.0
    # A -> B
    rd = ReactionDiffusion(2, [[0]], [[1]], [k], N, D=[0.0, 0.0],
                           logy=True, logt=True)
    fref = np.array([(-k*t0, t0*k*y0[i*2]/y0[i*2+1])
                     for i in range(N)]).flatten()
    _test_f_and_dense_jac_rmaj(rd, np.log(t0), np.log(y0), fref)


@pytest.mark.parametrize("N", [1, 3, 4, 5])
def test_ReactionDiffusion__only_1_reaction_bin_k_factor(N):
    y0 = np.concatenate([np.array([2.0, 3.0])/(x+1) for x in range(N)])
    k = 5.0
    # A -> B
    rd = ReactionDiffusion(2, [[0]], [[1]], [k], N, D=[0.0, 0.0],
                           bin_k_factor=[[x + 1] for x in range(N)],
                           bin_k_factor_span=[1])
    fref = [-10.0, 10.0]*N
    _test_f_and_dense_jac_rmaj(rd, 0.0, y0, fref)


@pytest.mark.parametrize("N", [1, 3, 4, 5])
def test_ReactionDiffusion__only_1_reaction_bin_k_factor_logy(N):
    y0 = np.concatenate([np.array([2.0, 3.0])/(x+1) for x in range(N)])
    k = 5.0
    # A -> B

    rd = ReactionDiffusion(2, [[0]], [[1]], [k], N, D=[0.0, 0.0],
                           bin_k_factor=[[x+1] for x in range(N)],
                           bin_k_factor_span=[1], logy=True)

    def k_(bi):
        return k*(bi+1)

    fref = np.array([(-k_(i), k_(i)*y0[i*2]/y0[i*2+1])
                     for i in range(N)]).flatten()
    _test_f_and_dense_jac_rmaj(rd, 0, np.log(y0), fref)


@pytest.mark.parametrize("N", [1, 3, 4, 5])
def test_ReactionDiffusion__only_1_reaction_bin_k_factor_logy_logt(N):
    t0 = 3.0
    y0 = np.concatenate([np.array([2.0, 3.0])/(x+1) for x in range(N)])
    k = 5.0
    # A -> B

    rd = ReactionDiffusion(2, [[0]], [[1]], [k], N, D=[0.0, 0.0],
                           bin_k_factor=[[x+1] for x in range(N)],
                           bin_k_factor_span=[1], logy=True, logt=True)

    def k_(bi):
        return k*(bi+1)

    fref = np.array([(-k_(i)*t0, k_(i)*t0*y0[i*2]/y0[i*2+1])
                     for i in range(N)]).flatten()
    _test_f_and_dense_jac_rmaj(rd, np.log(t0), np.log(y0), fref)


@pytest.mark.parametrize("log", TRUE_FALSE_PAIRS)
def test_ReactionDiffusion__only_1_species_diffusion_3bins(log):
    # Diffusion without reaction
    # 3 bins
    t0 = 3.0
    logy, logt = log
    D = 17.0
    y0 = np.array([23.0, 27.0, 37.0])
    N = 3
    x = [5.0, 7.0, 13.0, 15.0]
    xc = [4.0, 6.0, 10.0, 14.0, 16.0]
    nstencil = 3
    rd = ReactionDiffusion(1, [], [], [], D=[D], x=x, N=N, logy=logy,
                           logt=logt, lrefl=False, rrefl=False,
                           nstencil=nstencil)
    assert np.allclose(rd._xc, xc)

    w = [1/16, -1/8, 1/16]  # finite diff. weights for 2nd order deriv
    for i in range(N):
        assert np.allclose(rd.D_weight[i*nstencil:(i+1)*nstencil], w)
    J = D*(w[0]*y0[0] + w[1]*y0[1] + w[2]*y0[2])
    fref = np.array([J, J, J])

    if logy:
        fref /= y0
    if logt:
        fref *= t0

    if logy:
        jref = D*np.array([  # jref[i, k] = ...
            [w[k]*y0[k]/y0[i] if k != i else -1/y0[k]*sum([
                w[j]*y0[j] if j != k else 0 for j in range(3)
            ]) for k in range(3)] for i in range(3)
        ])
        jref[0, 2] = 0.0  # dense_jac_rmaj only computes banded approx.
        jref[2, 0] = 0.0  # same as above.
    else:
        jref = D*np.array([[w[k] if abs(k-i) < 2 else 0.0 for
                          k in range(3)] for i in range(3)])

    if logt:
        jref *= t0

    y = np.log(y0) if logy else y0
    t = np.log(t0) if logt else t0
    _test_f_and_dense_jac_rmaj(rd, t, y, fref, jref)

    jout_bnd = np.zeros((3, 3), order='F')
    rd.banded_packed_jac_cmaj(t, y, jout_bnd)
    jref_bnd = get_banded(jref, 1, 3)
    assert np.allclose(jout_bnd, jref_bnd)


def test_ReactionDiffusion__D_weight():
    x = np.array([2, 4, 6, 8, 10, 12, 14, 16], dtype=np.float64)
    # xc = x[:-1] + np.diff(x)/2
    rd = ReactionDiffusion(1, [], [], [], D=[1], x=x, nstencil=3,
                           lrefl=False, rrefl=False)
    assert np.allclose(rd.D_weight, np.array([
        [1/4, -1/2, 1/4],
        [1/4, -1/2, 1/4],
        [1/4, -1/2, 1/4],
        [1/4, -1/2, 1/4],
        [1/4, -1/2, 1/4],
        [1/4, -1/2, 1/4],
        [1/4, -1/2, 1/4]
    ]).flatten())

    rd = ReactionDiffusion(1, [], [], [], D=[1], x=x, nstencil=5,
                           lrefl=False, rrefl=False)
    assert np.allclose(rd.D_weight, np.array([
        [35/48, -13/6, 19/8, -7/6, 11/48],
        [11/48, -5/12, 1/8, 1/12, -1/48],
        [-1/48, 1/3, -5/8, 1/3, -1/48],
        [-1/48, 1/3, -5/8, 1/3, -1/48],
        [-1/48, 1/3, -5/8, 1/3, -1/48],
        [-1/48, 1/12, 1/8, -5/12, 11/48],
        [11/48, -7/6, 19/8, -13/6, 35/48]
    ]).flatten())


@slow
@pytest.mark.parametrize("log", TRUE_FALSE_PAIRS)
def test_ReactionDiffusion__only_1_species_diffusion_7bins(log):
    # Diffusion without reaction
    N = 7
    nstencil = 5
    nsidep = (nstencil-1)//2
    t0 = 3.0
    logy, logt = log
    D = 2.0
    y0 = np.array([12, 8, 11, 5, 7, 4, 9], dtype=np.float64)
    x = np.array([3, 5, 13, 17, 23, 25, 35, 37], dtype=np.float64)
    rd = ReactionDiffusion(1, [], [], [], D=[D], x=x,
                           logy=logy, logt=logt, nstencil=nstencil,
                           lrefl=False, rrefl=False)
    weights = [
        [951/8800, -716/2475, 100/297, -75/352, 311/5400],
        [321/8800, -161/2475, 7/297, 3/352, -19/5400],
        [-39/8800, 109/2475, -127/1485, 87/1760, -19/5400],
        [-2/693, 38/675, -129/1100, 7/108, -1/1050],
        [0, 9/160, -7/72, 2/45, -1/288],
        [-8/1575, 9/400, 0, -19/450, 25/1008],
        [16/315, -9/32, 31/72, -13/45, 179/2016]
    ]
    assert np.allclose(rd.D_weight, np.array(weights).flatten())

    lb = stencil_pxci_lbounds(nstencil, N)
    yi = pxci_to_bi(nstencil, N)
    fref = np.array([sum([D*weights[i][j]*y0[yi[j+lb[i]]] for j
                          in range(nstencil)]) for i in range(N)])

    if logy:
        fref /= y0
    if logt:
        fref *= t0

    jref = np.zeros((N, N))
    for i in range(N):
        for j in range(max(0, i-1), min(N, i+2)):
            if logy:
                if j == i+1 or j == i-1:
                    for k in range(nstencil):
                        if yi[k+lb[i]] == j:
                            jref[i, j] += D*weights[i][k]*y0[j]/y0[i]
                else:  # j == i
                    assert i == j
                    for k in range(nstencil):
                        cyi = yi[k+lb[i]]
                        if i == cyi:
                            continue
                        jref[i, i] -= D*weights[i][k]*y0[cyi]/y0[i]
            else:
                if i-1 <= j and j <= i+1:
                    jref[i, j] = D*weights[i][j-lb[i]+nsidep]
    if logt:
        jref *= t0
    t = np.log(t0) if logt else t0
    y = np.log(y0) if logy else y0
    _test_f_and_dense_jac_rmaj(rd, t, y, fref, jref)

    jout_bnd = np.zeros((3, N), order='F')
    rd.banded_packed_jac_cmaj(t, y, jout_bnd)
    jref_bnd = get_banded(jref, 1, N)
    assert np.allclose(jout_bnd, jref_bnd)

    jout_cmprs = rd.alloc_jout_compressed(nsidep)
    rd.compressed_jac_cmaj(t, y, jout_cmprs)
    jref_cmprs = get_compressed(jref, 1, N, nsidep)
    assert np.allclose(jout_cmprs, jref_cmprs)


@slow
@pytest.mark.parametrize("geom_refl", list(product(
    (FLAT, CYLINDRICAL, SPHERICAL), TRUE_FALSE_PAIRS)))
def test_ReactionDiffusion__3_reactions_4_species_5_bins_k_factor(geom_refl):
    # TODO: add logy, logt
    from sympy import finite_diff_weights
    geom, refl = geom_refl
    lrefl, rrefl = refl
    # r[0]: A + B -> C
    # r[1]: D + C -> D + A + B
    # r[2]: B + B -> D
    #              r[0]     r[1]       r[2]
    stoich_reac = [[0, 1], [2, 3],    [1, 1]]
    stoich_prod = [[2],    [0, 1, 3], [3]]
    stoich_actv = stoich_reac
    n = 4
    N = 5
    D = np.array([2.6, 3.7, 5.11, 7.13])*213
    y0 = np.array([
        2.5, 1.2, 3.2, 4.3,
        2.7, 0.8, 1.6, 2.4,
        3.1, 0.3, 1.5, 1.8,
        3.3, 0.6, 1.6, 1.4,
        3.6, 0.9, 1.7, 1.2
    ]).reshape((5, 4))
    x = np.array([11.0, 13.3, 17.0, 23.2, 29.8, 37.2])
    xc_ = x[:-1]+np.diff(x)/2
    xc_ = [x[0]-(xc_[0]-x[0])]+list(xc_)+[x[-1]+(x[-1]-xc_[-1])]
    assert len(xc_) == 7
    k = [31.0, 37.0, 41.0]

    # (r[0], r[1]) modulations over bins
    bin_k_factor = [(i+3, i+4) for i in range(N)]
    bin_k_factor_span = [1, 1]
    nstencil = 3
    nsidep = 1
    rd = ReactionDiffusion(
        4, stoich_reac, stoich_prod, k, N, D=D, x=x,
        bin_k_factor=bin_k_factor,
        bin_k_factor_span=bin_k_factor_span, geom=geom,
        nstencil=nstencil, lrefl=lrefl, rrefl=rrefl)

    assert np.allclose(xc_, rd._xc)

    lb = stencil_pxci_lbounds(nstencil, N, lrefl, rrefl)
    if lrefl:
        if rrefl:
            assert lb == [0, 1, 2, 3, 4]
        else:
            assert lb == [0, 1, 2, 3, 3]
    else:
        if rrefl:
            assert lb == [1, 1, 2, 3, 4]
        else:
            assert lb == [1, 1, 2, 3, 3]
    assert lb == list(map(rd._stencil_bi_lbound, range(N)))

    pxci2bi = pxci_to_bi(nstencil, N)
    assert pxci2bi == [0, 0, 1, 2, 3, 4, 4]
    assert pxci2bi == list(map(rd._xc_bi_map, range(N+2)))

    D_weight = []
    for bi in range(N):
        local_x_serie = xc_[lb[bi]:lb[bi]+nstencil]
        local_x_around = xc_[nsidep+bi]
        w = finite_diff_weights(
            2, local_x_serie, x0=local_x_around
        )
        D_weight.append(w[-1][-1])
        if geom == FLAT:
            pass
        elif geom == CYLINDRICAL:
            for wi in range(nstencil):
                # first order derivative
                D_weight[bi][wi] += w[-2][-1][wi]*1/local_x_around
        elif geom == SPHERICAL:
            for wi in range(nstencil):
                # first order derivative
                D_weight[bi][wi] += w[-2][-1][wi]*2/local_x_around
        else:
            raise RuntimeError
    assert np.allclose(rd.D_weight, np.array(
        D_weight, dtype=np.float64).flatten())

    def cflux(si, bi):
        f = 0.0
        for k in range(nstencil):
            f += rd.D_weight[bi*nstencil+k]*y0[pxci2bi[lb[bi]+k], si]
        return D[si]*f

    r = [
        [k[0]*bin_k_factor[bi][0]*y0[bi, 0]*y0[bi, 1] for
         bi in range(N)],
        [k[1]*bin_k_factor[bi][1]*y0[bi, 3]*y0[bi, 2] for
         bi in range(N)],
        [k[2]*y0[bi, 1]**2 for bi in range(N)],
    ]

    fref = np.array([[
        -r[0][bi] + r[1][bi] + cflux(0, bi),
        -r[0][bi] + r[1][bi] - 2*r[2][bi] + cflux(1, bi),
        r[0][bi] - r[1][bi] + cflux(2, bi),
        r[2][bi] + cflux(3, bi)
    ] for bi in range(N)]).flatten()

    # Now let's check that the Jacobian is correctly computed.
    def dfdC(bi, lri, lci):
        v = 0.0
        for ri in range(len(stoich_reac)):
            totl = (stoich_prod[ri].count(lri) -
                    stoich_reac[ri].count(lri))
            if totl == 0:
                continue
            actv = stoich_actv[ri].count(lci)
            if actv == 0:
                continue
            v += actv*totl*r[ri][bi]/y0[bi, lci]
        return v

    def jac_elem(ri, ci):
        bri, bci = ri // n, ci // n
        lri, lci = ri % n,  ci % n
        elem = 0.0

        def _diffusion():
            _elem = 0.0
            for k in range(nstencil):
                if pxci2bi[lb[bri]+k] == bci:
                    _elem += D[lri]*rd.D_weight[bri*nstencil+k]
            return _elem

        if bri == bci:
            # on block diagonal
            elem += dfdC(bri, lri, lci)
            if lri == lci:
                elem += _diffusion()
        elif bri == bci - 1:
            if lri == lci:
                elem = _diffusion()
        elif bri == bci + 1:
            if lri == lci:
                elem = _diffusion()
        return elem

    jref = np.zeros((n*N, n*N), order='C')
    for ri, ci in np.ndindex(n*N, n*N):
        jref[ri, ci] = jac_elem(ri, ci)

    # Compare to what is calculated using our C++ callback
    _test_f_and_dense_jac_rmaj(rd, 0, y0.flatten(), fref, jref)

    jout_cmaj = np.zeros((n*N, n*N), order='F')
    rd.dense_jac_cmaj(0.0, y0.flatten(), jout_cmaj)
    assert np.allclose(jout_cmaj, jref)

    ref_banded_j = get_banded(jref, n, N)

    jout_bnd_packed_cmaj = np.zeros((2*n+1, n*N), order='F')
    rd.banded_packed_jac_cmaj(0.0, y0.flatten(), jout_bnd_packed_cmaj)

    if os.environ.get('plot_tests', False):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from chemreac.util.plotting import coloured_spy
        fig = plt.figure()
        ax = fig.add_subplot(3, 1, 1)
        coloured_spy(ref_banded_j, ax=ax)
        plt.title('ref_banded_j')
        ax = fig.add_subplot(3, 1, 2)
        coloured_spy(jout_bnd_packed_cmaj, ax=ax)
        plt.title('jout_bnd_packed_cmaj')
        ax = fig.add_subplot(3, 1, 3)
        coloured_spy(ref_banded_j-jout_bnd_packed_cmaj, ax=ax)
        plt.title('diff')
        plt.savefig(__file__+'.png')

    assert np.allclose(jout_bnd_packed_cmaj, ref_banded_j)

    jout_bnd_padded_cmaj = np.zeros((3*n+1, n*N), order='F')
    rd.banded_padded_jac_cmaj(0.0, y0.flatten(), jout_bnd_padded_cmaj)
    assert np.allclose(jout_bnd_padded_cmaj[n:, :], ref_banded_j)


@slow
@pytest.mark.parametrize("geom_refl", list(product(
    (FLAT, CYLINDRICAL, SPHERICAL), TRUE_FALSE_PAIRS)))
def test_diffusion_jac(geom_refl):
    geom, refl = geom_refl
    lrefl, rrefl = refl
    N = 9
    x = np.linspace(0.1, 1, N+1)
    rd = ReactionDiffusion(1, [], [], [], D=[3], N=N, x=x, nstencil=3,
                           lrefl=lrefl, rrefl=rrefl, geom=geom)
    y0 = x[0]+2*x[1:]**2/(1+x[1:]**4)
    # compare f and jac with Symbolic class:
    _test_f_and_dense_jac_rmaj(rd, 0, y0)


COMBOS = list(product((FLAT, CYLINDRICAL, SPHERICAL), TR_FLS))


@pytest.mark.parametrize("params", COMBOS)
def test_integrated_conc(params):
    geom, logx = params
    N = 8192
    x0, xend = 0.11, 1.37
    x = np.linspace(x0, xend, N+1)
    rd = ReactionDiffusion(1, [], [], [], D=[0], N=N,
                           x=np.log(x) if logx else x, geom=geom, logx=logx)
    xc = np.exp(rd.xcenters) if logx else rd.xcenters
    y = xc*np.exp(-xc)

    def primitive(t):
        if geom == FLAT:
            return -(t+1)*np.exp(-t)
        elif geom == CYLINDRICAL:
            return 2*np.exp(-t)*np.pi*(-2 - 2*t - t**2)
        elif geom == SPHERICAL:
            return 4*np.exp(-t)*np.pi*(-6 - 6*t - 3*t**2 - t**3)
        else:
            raise NotImplementedError
    res = rd.integrated_conc(y)
    ref = (primitive(xend) - primitive(x0))
    assert abs(res - ref) < 1e-8
