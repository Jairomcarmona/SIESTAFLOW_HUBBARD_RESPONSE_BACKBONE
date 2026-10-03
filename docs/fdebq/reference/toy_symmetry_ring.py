"""Toy mean-field Hubbard ring: checks the response reconstruction law.

N sites, 1 orbital/site, collinear spin, Hartree mean field U n_{i,-s}, Fermi smearing.
Perturbation alpha*n_J (spin independent); observable n_I = n_up + n_dn.
SCREENED = self-consistent response; BARE = mean field frozen at the reference.
"""
import numpy as np

def solve(eps, U, t, Ne, kT, alpha, h_stag=None, frozen=None, it=4000, mix=0.3, seed_m=None):
    N = len(eps)
    H0 = np.diag(eps.astype(float)) + alpha
    for i in range(N):
        H0[i, (i+1) % N] = H0[(i+1) % N, i] = -t
    for i in range(N):  # next-nearest hopping breaks bipartite particle-hole symmetry
        j = (i+2) % N
        if j != i: H0[i, j] = H0[j, i] = -0.3*t
    nup = np.full(N, Ne/(2*N)); ndn = nup.copy()
    if seed_m is not None:
        nup = nup + 0.3*seed_m; ndn = ndn - 0.3*seed_m
    def occ(Hu, Hd):
        eu, vu = np.linalg.eigh(Hu); ed, vd = np.linalg.eigh(Hd)
        e = np.concatenate([eu, ed])
        lo, hi = e.min()-10, e.max()+10
        for _ in range(200):
            mu = 0.5*(lo+hi)
            f = 1/(1+np.exp(np.clip((e-mu)/kT, -500, 500)))
            if f.sum() > Ne: hi = mu
            else: lo = mu
        fu, fd = f[:N], f[N:]
        return (vu**2) @ fu, (vd**2) @ fd
    if frozen is not None:
        mu_up, mu_dn = frozen
        return occ(H0 + np.diag(U*mu_dn), H0 + np.diag(U*mu_up))
    for _ in range(it):
        Hu = H0 + np.diag(U*ndn + (h_stag if h_stag is not None else 0))
        Hd = H0 + np.diag(U*nup - (h_stag if h_stag is not None else 0))
        nu2, nd2 = occ(Hu, Hd)
        if max(abs(nu2-nup).max(), abs(nd2-ndn).max()) < 1e-13:
            break
        nup, ndn = (1-mix)*nup+mix*nu2, (1-mix)*ndn+mix*nd2
    return nup, ndn

def chi(eps, U, t, Ne, kT, seed_m, a=1e-4):
    N = len(eps)
    ref = solve(eps, U, t, Ne, kT, 0*np.eye(N), seed_m=seed_m)
    C0 = np.zeros((N, N)); C = np.zeros((N, N))
    for J in range(N):
        A = np.zeros((N, N)); A[J, J] = a
        sp = solve(eps, U, t, Ne, kT, A, seed_m=seed_m)
        sm = solve(eps, U, t, Ne, kT, -A, seed_m=seed_m)
        C[:, J] = ((sp[0]+sp[1]) - (sm[0]+sm[1]))/(2*a)
        bp = solve(eps, U, t, Ne, kT, A, frozen=ref)
        bm = solve(eps, U, t, Ne, kT, -A, frozen=ref)
        C0[:, J] = ((bp[0]+bp[1]) - (bm[0]+bm[1]))/(2*a)
    return ref, C0, C

def check(name, eps, seed, perm):
    ref, C0, C = chi(np.array(eps), U=4.0, t=1.0, Ne=len(eps), kT=0.05, seed_m=np.array(seed))
    m = ref[0]-ref[1]
    P = np.zeros((len(eps),)*2)
    for i, j in enumerate(perm): P[j, i] = 1
    d0 = np.abs(P@C0@P.T - C0).max(); d = np.abs(P@C@P.T - C).max()
    eps_sign = np.sign(np.dot(m[list(perm)], m)) if np.abs(m).max() > 1e-8 else 0
    print(f"{name:42s} moments={np.round(m,4)} max|P chi0 P^T - chi0|={d0:.1e} max|P chi P^T - chi|={d:.1e}")

N = 4
check("AFM ring, translation+spin flip (g: i->i+1)", [0]*N, [1, -1, 1, -1], [1, 2, 3, 0])
check("AFM ring, pure translation (g: i->i+2)", [0]*N, [1, -1, 1, -1], [2, 3, 0, 1])
check("ferrimagnet (eps alternating), i->i+1", [0, 0.8, 0, 0.8], [1, -1, 1, -1], [1, 2, 3, 0])
check("ferrimagnet (eps alternating), i->i+2", [0, 0.8, 0, 0.8], [1, -1, 1, -1], [2, 3, 0, 1])
check("FM ring, i->i+1", [0]*N, [1, 1, 1, 1], [1, 2, 3, 0])
N = 6
check("6-ring AFM, i->i+1 (spin flip)", [0]*N, [1,-1,1,-1,1,-1], [1,2,3,4,5,0])
check("6-ring AFM + site energies 0/0.8, i->i+1", [0,0.8]*3, [1,-1,1,-1,1,-1], [1,2,3,4,5,0])
check("6-ring AFM + site energies 0/0.8, i->i+2", [0,0.8]*3, [1,-1,1,-1,1,-1], [2,3,4,5,0,1])
check("6-ring uudd-like (broken), i->i+1", [0]*N, [1,1,-1,1,1,-1], [1,2,3,4,5,0])
