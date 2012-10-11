#!/usr/bin/env python

from argparse import ArgumentParser
import matplotlib.pyplot as pp
import numpy as np
import os
import parameters as pr
import ptsampler as pt
import scipy.stats as ss
import scipy.stats.mstats as ssm

def do_plot(ichain, name, tname, true, outdir, mmin=None, mmax=None, periodic=False):
    xs=np.linspace(np.amin(ichain), np.amax(ichain), 1000)
        
    mu=np.mean(ichain.flatten())
    q90=ssm.mquantiles(ichain.flatten(), prob=[0.05, 0.95], alphap=1.0/3.0, betap=1.0/3.0)-mu

    kde=ss.gaussian_kde(ichain.flatten())

    ys=kde(xs)

    if not periodic:
        if mmin is not None:
            ys += kde(2.0*mmin - xs)
        if mmax is not None:
            ys += kde(2.0*mmax - xs)
    else:
        dx = mmax - mmin
        ys += kde(xs - dx)
        ys += kde(xs + dx)

    pp.subplot(2,1,1)
    pp.plot(xs, ys)

    if true is not None:
        pp.axvline(true, color='k')

    pp.xlabel('$' + tname + '$')
    pp.ylabel(r'$p\left(' + tname + r'\right)$')
    pp.title('$' + tname + '$: $%g^{+%g}_{%g}$'%(mu, q90[1], q90[0]))

    pp.axvline(mu)
    pp.axvline(q90[0]+mu, linestyle='--')
    pp.axvline(q90[1]+mu, linestyle='--')

    pp.subplot(2,1,2)
    pp.plot(np.mean(ichain, axis=1))

    if true is not None:
        pp.axhline(true, color='k')

    pp.ylabel(r'$\left \langle' + tname + r'\right \rangle $')
    pp.xlabel('Iteration Number')

    if outdir is not None:
        pp.savefig(os.path.join(args.outdir, name + '.pdf'))

    pp.show()
    

if __name__ == '__main__':
    parser=ArgumentParser()

    parser.add_argument('--input', metavar='FILE', required=True, help='input chain')
    parser.add_argument('--outdir', metavar='DIR', default=None, help='output directory')
    parser.add_argument('--trueparams', metavar='FILE', default=None, help='true parameters')

    parser.add_argument('--fburnin', metavar='F', default=0.1, type=float, help='fraction to discard as burned in')

    parser.add_argument('--nwalkers', metavar='N', default=100, type=int, help='number of ensemble walkers')

    args=parser.parse_args()

    pts=np.loadtxt(args.input)

    # (Nsamples, Ntemps, Nwalkers, Ndim)
    pts=np.reshape(pts, (-1, args.nwalkers, pts.shape[-1]))

    logls=pts[..., 0]
    chain=pr.Parameters(pts[..., 2:])

    logls=pt.burned_in_samples(logls, fburnin=args.fburnin)
    chain=pt.decorrelated_samples(pt.burned_in_samples(chain, fburnin=args.fburnin))

    names=chain.header.split()[1:]
    tnames=chain.tex_header

    if args.trueparams is not None:
        true=pr.Parameters(np.loadtxt(args.trueparams))
    else:
        true=[None for i in range(chain.shape[-1])]

    try:
        if args.outdir is not None:
            os.makedirs(args.outdir)
    except:
        # Ignore errors
        pass

    # logls
    pp.plot(np.mean(logls, axis=1))
    pp.title(r'$\log \mathcal{L}$')
    pp.ylabel(r'$\left \langle \log \mathcal{L} \right \rangle$')
    pp.xlabel('Iteration Number')
    if args.outdir is not None:
        pp.savefig(os.path.join(args.outdir, 'logl.pdf'))
    pp.show()

    i = 0
    for iobs in range(chain.nobs):
        do_plot(chain.V[...,iobs], names[i], tnames[i], true[i], args.outdir)
        i += 1

        do_plot(chain.sigma[...,iobs], names[i], tnames[i], true[i], args.outdir, mmin=0.0)
        i += 1

        do_plot(chain.tau[...,iobs], names[i], tnames[i], true[i], args.outdir, mmin=0.0)
        i += 1

    for ipl in range(chain.npl):
        do_plot(chain.K[...,iobs], names[i], tnames[i], true[i], args.outdir)
        i += 1

        do_plot(chain.n[...,iobs], names[i], tnames[i], true[i], args.outdir, mmin=0.0)
        if true[i] is not None:
            ptrue=2.0*np.pi/true[i]
        else:
            ptrue=None
        do_plot(chain.P[...,iobs], 
                names[i].replace('n', 'P'),
                tnames[i].replace('n', 'P'),
                ptrue,
                args.outdir,
                mmin=0.0)
        i += 1

        do_plot(chain.chi[...,iobs], names[i], tnames[i], true[i], args.outdir, mmin=0.0, mmax=1.0, periodic=True)
        i += 1

        do_plot(chain.e[...,iobs], names[i], tnames[i], true[i], args.outdir, mmin=0.0, mmax=1.0)
        i += 1

        do_plot(chain.omega[...,iobs], names[i], tnames[i], true[i], args.outdir, mmin=0.0, mmax=2.0*np.pi, periodic=True)
        i += 1
