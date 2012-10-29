import numpy as np
import numpy.linalg as nl
import numpy.random as nr
import parameters as params
import rv_model as rv
import scipy.linalg as sl

def correlated_gaussian_loglikelihood(xs, means, cov):
    """Returns the likelihood for data xs, assumed to be multivariate
    Gaussian with the given means and covariance."""
    lu,piv=sl.lu_factor(cov)

    lambdas=np.diag(lu)

    ndim=xs.shape[0]
    
    ds=(xs-means)*sl.lu_solve((lu,piv), xs-means)/2.0

    return -np.log(2.0*np.pi)*(ndim/2.0)-0.5*np.sum(np.log(lambdas))-np.sum(ds)

def generate_covariance(ts, sigma, tau):
    """Generates a covariance matrix according to an exponential
    autocovariance: cov(t_i, t_j) =
    sigma*sigma*exp(-|ti-tj|/tau)."""

    ndim = ts.shape[0]

    tis = np.tile(np.reshape(ts, (-1, 1)), (1, ndim))
    tjs = np.tile(ts, (ndim, 1))

    return sigma*sigma*np.exp(-np.abs(tis-tjs)/tau)

class LogPrior(object):
    """Log of the prior function."""

    def __init__(self, pmin=None, pmax=None, npl=1, nobs=1):
        """Initialize with the given bounds on the priors."""

        if pmin is None:
            self._pmin = params.Parameters(npl=npl, nobs=nobs)
            self._pmin = 0.0*self._pmin
            self._pmin.V = float('-inf')
        else:
            self._pmin = pmin

        if pmax is None:
            self._pmax = params.Parameters(npl=npl, nobs=nobs)
            self._pmax = self._pmax + float('inf')
            self._pmax.chi = 1.0
            self._pmax.e = 1.0
            self._pmax.omega = 2.0*np.pi
        else:
            self._pmax = pmax

        self._npl = npl
        self._nobs = nobs

    def __call__(self, p):
        p = params.Parameters(p, npl=self._npl, nobs=self._nobs)

        # Check bounds
        if np.any(p <= self._pmin) or np.any(p >= self._pmax):
            return float('-inf')

        # Ensure unique labeling of planets: in increasing order of
        # period
        if p.npl > 1 and np.any(p.P[1:] < p.P[:-1]):
            return float('-inf')

        pr=0.0

        # Uniform prior on velocity offset

        # Jeffreys scale prior on sigma
        for s in p.sigma:
            pr -= np.sum(np.log(s))

        # Jeffreys scale prior on tau
        for t in p.tau:
            pr -= np.sum(np.log(t))

        # Jeffreys scale prior on K
        for k in p.K:
            pr -= np.sum(np.log(k))

        # Jeffreys scale prior on n
        for n in p.n:
            pr -= np.sum(np.log(n))

        # Uniform prior on chi

        # Thermal prior on e
        for e in p.e:
            pr += np.sum(np.log(e))

        # Uniform prior on omega

        return pr

class LogLikelihood(object):
    """Log likelihood."""
    def __init__(self, ts, rvs):
        self._ts = ts
        self._rvs = rvs

    @property
    def ts(self):
        return self._ts

    @property
    def rvs(self):
        return self._rvs

    def __call__(self, p):
        nobs=len(self.rvs)
        npl=(p.shape[-1]-3*nobs)/5

        p = params.Parameters(p, nobs=nobs, npl=npl)

        ll=0.0

        for t, rvobs, V, sigma, tau in zip(self.ts, self.rvs, p.V, p.sigma, p.tau):
            if npl == 0:
                rvmodel=np.zeros_like(t)
            else:
                rvmodel=np.sum(rv.rv_model(t, p), axis=0)

            residual=rvobs-rvmodel
            cov=generate_covariance(t, sigma, tau)

            ll += correlated_gaussian_loglikelihood(residual, V*np.ones_like(residual), cov)

        return ll
            
def prior_bounds_from_data(npl, ts, rvs):
    """Returns conservative prior bounds (pmin, pmax) given sampling
    times for each observatory."""

    nobs=len(ts)

    dts=[np.diff(t) for t in ts]
    min_dt=reduce(min, [np.min(dt) for dt in dts])

    tobss=[t[-1]-t[0] for t in ts]
    max_obst=reduce(max, tobss)

    min_dv=reduce(min, [np.min(np.abs(np.diff(rv))) for rv in rvs])

    maxspread=reduce(max, [np.max(rv)-np.min(rv) for rv in rvs])

    pmin=params.Parameters(nobs=nobs,npl=npl)
    pmax=params.Parameters(nobs=nobs,npl=npl)

    Vmin=[]
    Vmax=[]
    taumin=[]
    taumax=[]
    sigmamin=[]
    sigmamax=[]
    for t,rv in zip(ts, rvs):
        spread=np.max(rv) - np.min(rv)
        Vmin.append(np.min(rv) - spread)
        Vmax.append(np.max(rv) + spread)

        mindt=np.min(np.diff(t))
        T=t[-1] - t[0]

        taumin.append(mindt/10.0)
        taumax.append(T*10.0)

        sigmamin.append(0.0)
        sigmamax.append(2.0*np.std(rv))

    pmin.V = np.array(Vmin)
    pmax.V = np.array(Vmax)
    pmin.tau = np.array(taumin)
    pmax.tau = np.array(taumax)
    pmin.sigma = np.array(sigmamin)
    pmax.sigma = np.array(sigmamax)

    if npl >= 1:
        pmin.n = 2.0*np.pi/(max_obst)
        pmax.n = 2.0*np.pi/(min_dt)

        pmin.chi = 0.0
        pmax.chi = 1.0
        
        pmin.e = 0.0
        pmax.e = 1.0
    
        pmin.omega = 0.0
        pmax.omega = 2.0*np.pi

        pmin.K = min_dv
        pmax.K = 2.0*maxspread

    return pmin, pmax

def draw_logarithmic(low, high, size=1):
    llow = np.log(low)
    lhigh = np.log(high)

    return np.exp(nr.uniform(low=llow, high=lhigh, size=size))

def generate_initial_sample(pmin, pmax, ntemps, nwalkers):
    """Generates an initial sample of parameters drawn uniformly from
    the prior ."""

    npl = pmin.npl
    nobs = pmin.nobs

    assert npl == pmax.npl, 'Number of planets must agree in prior bounds'
    assert nobs == pmax.nobs, 'Number of observations must agree in prior bounds'

    N = pmin.shape[-1]

    samps=params.Parameters(arr=np.zeros((ntemps, nwalkers, N)), nobs=nobs, npl=npl)

    V=samps.V
    tau=samps.tau
    sigma=samps.sigma
    for i in range(nobs):
        V[:,:,i] = nr.uniform(low=pmin.V[i], high=pmax.V[i], size=(ntemps, nwalkers))
        tau[:,:,i] = draw_logarithmic(low=pmin.tau[i], high=pmax.tau[i], size=(ntemps,nwalkers))
        sigma[:,:,i] = draw_logarithmic(low=pmax.sigma[i]/1000.0, high=pmax.sigma[i], size=(ntemps,nwalkers))
    samps.V=V
    samps.tau = tau
    samps.sigma = sigma

    if npl >= 1:
        samps.K = draw_logarithmic(low=pmin.K[0], high=pmax.K[0], size=(ntemps, nwalkers, npl))

        # Make sure that periods are increasing
        samps.n = np.sort(draw_logarithmic(low=pmin.n, high=pmax.n, size=(ntemps,nwalkers,npl)))[:,:,::-1]

        samps.e = nr.uniform(low=0.0, high=1.0, size=(ntemps, nwalkers,npl))
        samps.chi = nr.uniform(low=0.0, high=1.0, size=(ntemps, nwalkers,npl))
        samps.omega = nr.uniform(low=0.0, high=2.0*np.pi, size=(ntemps, nwalkers,npl))

    return samps

def recenter_samples(ts, chains, logls, sigmafactor=0.1):
    """Generates a suite of samples around the maximum likelihood
    point in chains, with a reasonable error distribution."""

    sf=sigmafactor

    T=ts[-1]-ts[0]
    
    ibest=np.argmax(logls)
    p0=params.Parameters(np.reshape(chains, (-1, chains.shape[-1]))[ibest, :])

    ncycle=T/p0.P
    ncorr=T/p0.tau
    nobs=len(ts)

    samples=params.Parameters(np.copy(chains))

    assert samples.npl == 1, 'require exactly one planet'
    assert samples.nobs == 1, 'require exactly one observatory'

    samples.V = np.random.normal(loc=p0.V, scale=sf*p0.sigma/np.sqrt(nobs), size=samples.V.shape)
    samples.sigma = np.random.lognormal(mean=np.log(p0.sigma), sigma=sf/np.sqrt(ncorr), size=samples.sigma.shape)
    samples.tau = np.random.lognormal(mean=np.log(p0.tau), sigma=sf/np.sqrt(ncorr), size=samples.tau.shape)
    samples.K = np.random.normal(loc=p0.K, scale=sf*p0.K/np.sqrt(nobs), size=samples.K.shape)
    samples.n = np.random.lognormal(mean=np.log(p0.n), sigma=sf/np.sqrt(ncycle), size=samples.n.shape)
    samples.chi = np.random.lognormal(mean=np.log(p0.chi), sigma=sf/np.sqrt(ncycle), size=samples.chi.shape)
    samples.e = np.random.lognormal(mean=np.log(p0.e), sigma=sf/np.sqrt(ncycle), size=samples.e.shape)
    samples.omega = np.random.lognormal(mean=np.log(p0.omega), sigma=sf/np.sqrt(ncycle), size=samples.omega.shape)

    return samples
    
