'''
Created on Oct 2, 2009

@author: michel
'''
from scipy import optimize
import numpy

def line_func(res, p):
    return p[0] * res + p[1]

def linear_fit(x,y):
    def _err(p,x,y):
        yc = line_func(x, p)
        return y-yc
    
    p0 = [0,0]
    p1, res = optimize.leastsq(_err, p0, args=(numpy.array(x), numpy.array(y)))
    return p1