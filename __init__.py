"""Fire Simulation Library for Fire on the Fringe SESYNC Pursuit"""

import sys
sys.dont_write_bytecode = True
import numpy as np
import numba
import math


# Aliases for more readable code
BARE = 0
INFLAMMABLE = 0
UNBURNED = 0

def fill_L(B, p, L):
    """Fill a LandCover (L) map from a Biome map (B).
    
    Arguments:
        B - 2d numpy.ndarray(int)
            Spatial grid of Biome classes for each pixel.
        
        p - tuple(tuple(int))
            The proportion of different landcover classes within each Biome.
            p[b][l] is the proportion of Biome 'b' that is made up of
            landcover component l. The length of p should be equal to the
            number of biomes. The length of each *element* of p should be 
            equal to the number of distinct landcover classes.

        L* - 2d numpy.ndarray(int)
            Land cover drawn from the distributions in t corresponding to each
            Biome type. Must be identical in shape to B.
    """
    assert B.shape == L.shape
    for biome in range(len(p)):
        proportions = p[biome] # Proportion of each land cover class in this biome
        y,x = np.where(B==biome)
        L[y,x] = np.random.choice(len(proportions),y.size,p=proportions)


def fill_A(L, rngs, A):
    """Fill the Activation Energy map (A) with randomly generated values.
    
    Arguments:
        N_COVERS - int
            The number of landcover types in the simulation.
        
        L - 2d numpy.ndarray(int)
            2d map of andcover component type (e.g. bare, grass, etc.)

        rngs - tuple(callables)
            A sequence of callable objects (e.g. functions). There should
            be one entry in rngs for each landcover component class. Each
            callable rngs[l] in rngs should take one parameter, an int n,
            and return n random values of A corresponding to the
            landcover l.

        A* - 2d numpy.ndarray(int)
            The array to be filled with random activation energies based
            on the land cover component.
    """
    for lc in range(len(rngs)):
        y,x = np.where(L==lc)
        if len(y):
            A[y,x] = rngs[lc](y.size)


def fill_R(L, rngs, R):
    """Fill the Release Energy map (R) with randomly generated values.
    
    Arguments:
        N_COVERS - int
            The number of landcover types in the simulation.
        
        L - 2d numpy.ndarray(int)
            2d map of andcover component type (e.g. bare, grass, etc.)

        rngs - tuple(callables)
            A sequence of callable objects (e.g. functions). There should
            be one entry in rngs for each landcover component class. Each
            callable rngs[l] in rngs should take one parameter, an int n,
            and return n random values of R corresponding to the
            landcover l.

        A* - 2d numpy.ndarray(int)
            The array to be filled with random activation energies based
            on the land cover component.
    """
    fill_A(L, rngs, R)  # Same functionality as fill_A


@numba.jit(nopython=True)
def euclidean_distance(y1,x1,y2,x2):
    '''Find the Euclidean distance between two points'''
    return math.sqrt( ((x1-x2)*(x1-x2)) + ((y1-y2)*(y1-y2)) )


@numba.jit(nopython=True)
def weight_distance(dist):
    """How do we weight transmitted energy with distance?"""
    return 1/(dist*dist)


_MAX_KERNEL_RADIUS_ = 10
def find_kernel_denominator():
    """Find the denominator so that energy release integrates to 1."""
    total = 0
    for iy in range(-_MAX_KERNEL_RADIUS_,_MAX_KERNEL_RADIUS_+1):
        for ix in range(-_MAX_KERNEL_RADIUS_,_MAX_KERNEL_RADIUS_+1):
            if iy==0 and ix == 0:
                continue
            dist = euclidean_distance(0,0,iy,ix)
            if dist > _MAX_KERNEL_RADIUS_:
                continue
            total += weight_distance(dist)
    return total

_KERNEL_DENOMINATOR_ = find_kernel_denominator()  # Calc done on library import


@numba.jit(nopython=True)
def burn_next_active_pixel(fires, active, L, E, A, R, F):
    """Apply the Released Energy in a burnt pixel to neighbors.
    
    Arguments
        
        fires - tuple(numpy.ndarray(dtype=int))
            2-tuple of y and x coordinates of active or past fires
        active - tuple(ints)
            (start,end] coordinates of the currently burning fires
        L,E,A,R,F - Environmental fields (see Variable Descriptions).
    """
    Y, X = E.shape
    y, x = fires[0][active[0]], fires[1][active[0]]
    fire_time_step = F[y, x]
    
    for iy in range(y-_MAX_KERNEL_RADIUS_,y+_MAX_KERNEL_RADIUS_+1):
        if iy<0 or iy>=Y: continue
        for ix in range(x-_MAX_KERNEL_RADIUS_,x+_MAX_KERNEL_RADIUS_+1):
            
            # Bounds checking (or if this pixel has already been burned)
            if (ix < 0 or ix >= X or (y == iy and x == ix) or
                 (L[iy,ix] == INFLAMMABLE) or (F[iy,ix]>UNBURNED)):
                continue
            
            # If we're inside of max radius
            dist = euclidean_distance(y,x,iy,ix)
            if dist <= _MAX_KERNEL_RADIUS_:  # Apply the energy to the neighbor
                E[iy,ix] +=  (R[y,x] * weight_distance(dist) /
                              _KERNEL_DENOMINATOR_)
            
            # If we've exceeded Activation, add this pixel to the burn list
            if E[iy,ix] > A[iy,ix]:
                fires[0][active[1]] = iy
                fires[1][active[1]] = ix
                F[iy,ix] = fire_time_step + 1
                active[1] += 1
    
    active[0] += 1  # Set the next pixel as 'next'
    return active[0] < active[1]

    
@numba.jit(nopython=True)
def burn_next_iteration(fires, active, L, E, A, R, F):
    """Burn all active pixels in this time iteration (values in F)."""
    assert fires[0].size and fires[1].size
    iter_num = F[fires[0][active[0]], fires[1][active[0]]]
    if iter_num == UNBURNED:  # The cursor is already on an unburnt pixel
        return False
    while ( F[fires[0][active[0]], fires[1][active[0]]] == iter_num):
        burn_next_active_pixel(fires, active, L, E, A, R, F)
    return active[0] < active[1]


@numba.jit(nopython=True)
def burn_all(fires, active, L, E, A, R, F, n=-1):
    """Burn until there are no more active fires."""
    while n and (active[0] != active[1]):
        burn_next_active_pixel(fires, active, L, E, A, R, F)
        if n: n -= 1
        else: break
    return abs(n)


@numba.jit(nopython=True)
def ignite_fires(ignitions, fires, active, L, F):
    """Add active fires to the simulation.
    
    Parameters:
        locations - 2-tuple(numpy.ndarray(int))
            y,x locations for N ignition points.
        
        fires* - 2-tuple(numpy.ndarray(int))
            Tuple of y,x pixel coordinates of all fires. Ignitions will
            be added to the end of this list. cursor will be modified so
            that it points to one past the last new fire added to this list.
        
        cursor* - numpy.ndarray(int,shape=(2,))
            First and last+1 indices of active fires.
        
        F* - 2d numpy.array(bool)
            Map of burnt and burning pixels.
    """
    N = len(ignitions[0])
    n_added = 0
    for i in range(N):
        y, x = ignitions[0][i], ignitions[1][i]
        if L[y, x] == INFLAMMABLE or F[y, x]:
            continue
        n_added += 1
        fires[0][active[1]] = y
        fires[1][active[1]] = x
        F[y, x] = 1
        active[1] += 1
    return n_added


def fire_map_to_list(F, L):
    """Given F, build a list of fire eligible (based on L) fires.
    Fires that coincide with 0's in L are ineligible due to
    inflammability.
    """
    fires = np.where(F)
    eligible = (L[fires]).astype(bool)
    
    fires = fires[0][eligible], fires[1][eligible]
    active = np.array(len(fires[0]), dtype=int)
    return fires, active


"""A fire simulation."""
class Simulation:
    def __init__(self, B, L_distr, A_distr, R_distr):
        """Build the simulation with B and distributions for L A and R."""
        
        # Environmental Fields
        self.B = B.copy()
        
        assert all(len(lc)==len(L_distr[0]) for lc in L_distr)
        self.L_distr = L_distr
        
        self.A_distr = A_distr
        self.R_distr = R_distr
        self.L = np.zeros_like(B, dtype=int)
        
        # 'Energy' Fields
        self.E = np.zeros_like(B, dtype=float)
        self.A = np.zeros_like(B, dtype=float)
        self.R = np.zeros_like(B, dtype=float)
        self.F = np.zeros_like(B, dtype=int)
        
        # Fires
        self._fires = np.zeros(B.size,dtype=int), np.zeros(B.size,dtype=int)
        self.active = np.zeros(2, dtype=int)
        self.reset()
    
    
    @property
    def N_BIOMES(self):
        return len(L_distr)
    
    
    @property
    def N_LANDCOVERS(self):
        return len(L_distr[0])
    
    
    def resample_L(self):
        """Generate new L from the Band landcover distributions."""
        fill_L(self.B, self.L_distr, self.L)
        self.inflammable = np.where(L==0)
    
    
    def reset(self):
        """Generate new random fields for simulation."""
        self.iterations = 0
        self.resample_L()
        self.E[:] = 0.0
        self.E[self.L==0] = np.nan
        fill_A(self.L, self.A_distr, self.A)
        fill_R(self.L, self.R_distr, self.R)
        self.F[:] = 0
        self.active[:] = 0, 0
        self._fires[0][:] = 0
        self._fires[1][:] = 0
    
    
    def ignite_fires(self, ignitions):
        assert len(ignitions) == 2 and len(ignitions[0]) == len(ignitions[1])
        ignitions = np.array(ignitions[0]), np.array(ignitions[1])
        
        self.n_ignited = ignite_fires(ignitions, self._fires, self.active, self.L, self.F)
    
    
    def burn_next_pixel(self):
        return burn_next_active_pixel(self._fires, self.active, self.L,
                   self.E, self.A, self.R, self.F)
    
    
    def iterate(self):
        """Burn an iteration of fires."""
        self.iterations += 1
        return burn_next_iteration(self._fires, self.active, self.L, self.E,
                   self.A, self.R, self.F)
    
    
    def run(self, ignitions):
        """Ignite fires and burn until propagation halts."""
        self.reset()
        self.ignite_fires(ignitions)
        while self.iterate():
            pass
    
    
    def showF(self):
        F = self.F.astype(float)
        F[F==0] = np.nan
        imshow(F)
    
    
    def nancounts(self):
        print('E nan',np.sum(np.isnan(self.E)))
        print('A nan',np.sum(np.isnan(self.A)))
        print('R nan',np.sum(np.isnan(self.R)))
    
    
    @property
    def fires(self):
        return self._fires[0][:self.active[1]], self._fires[1][:self.active[1]]


def parameterize(distr, *p):
    """Parameterize a two-parameter distribution.
    
    Returns a callable distribution that takes one parameter,
        n, and returns n random samples.
    """
    def truncated_rng(n=1):
        """Truncated, parameterized distribution."""
        x = distr(*p, size=n)
        return x
    
    return truncated_rng


def visualize(fig, B, L, E, A, R, F, biome_labels=None, lc_labels=None):
    import matplotlib.pyplot as plt
    
    ax = fig.add_subplot(231)
    ax.imshow(B); ax.set_title('Biome')
    if biome_labels is not None:
        cbar = plt.colorbar(img, orientation='horizontal',
                      ticks=[i for i in range(len(biome_labels))])
        cbar.ax.set_xticklabels(biome_labels)
    

    ax = fig.add_subplot(232)
    ax.imshow(L); ax.set_title('Land Cover')
    if biome_labels is not None:
        cbar=ax.colorbar(img, orientation='horizontal',
                      ticks=[i for i in range(len(lc_labels))])
        cbar.ax.set_xticklabels(lc_labels)
    
    fig.add_subplot(233)
    not_nan = np.isfinite(A)
    pct = np.percentile(A[not_nan],99)
    img = ax.imshow(A); ax.set_title('Activation')
    img.set_clim(0,pct)
    plt.colorbar(img, orientation='horizontal')
    
    fig.add_subplot(234)
    ax.imshow(R); ax.set_title('Released')
    cbar=plt.colorbar(img, orientation='horizontal')

    fig.add_subplot(235)
    _f = np.copy(F).astype(float)
    _f[L==0] = np.nan
    img = ax.imshow(_f); ax.set_title('Fires')
    img.set_clim(0,1)
    plt.colorbar(img, orientation='horizontal',label='Burn Iteration')
    
    fig.add_subplot(236)
    img = ax.imshow(E); ax.set_title('Energy Accumulated');
    img.set_clim(0,pct)
    plt.colorbar(img, orientation='horizontal')