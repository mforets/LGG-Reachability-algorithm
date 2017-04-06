# This file was *autogenerated* from the file projections2.sage
from sage.all_cmdline import *   # import sage library
_sage_const_1 = Integer(1); _sage_const_0 = Integer(0); _sage_const_4 = Integer(4)
def lotov_algo (A, b, v1, v2, err, rel=_sage_const_1 ) :

    # init
    err = float (err)
    Mnd2d = Matrix ([v1, v2])
    M2dnd = Mnd2d.transpose ()

    # 1) first approximation
    dn2d = vector ([_sage_const_0 , _sage_const_1 ])
    dw2d = vector ([-_sage_const_1 , _sage_const_0 ])
    ds2d = vector ([_sage_const_0 , -_sage_const_1 ])
    de2d = vector ([_sage_const_1 , _sage_const_0 ])
    dnnd = M2dnd * dn2d
    dwnd = M2dnd * dw2d
    dsnd = M2dnd * ds2d
    dend = M2dnd * de2d

    # border points computation
    #print dnnd[0], ' ', dnnd[1], ' ', dnnd[2]
    n = Mnd2d * extreme_point (A, b, dnnd)
    w = Mnd2d * extreme_point (A, b, dwnd)
    s = Mnd2d * extreme_point (A, b, dsnd)
    e = Mnd2d * extreme_point (A, b, dend)
    # calculus of the bounding-box and epsilon if relative err
    if rel :
        xMin = w[_sage_const_0 ]
        xMax = e[_sage_const_0 ]
        yMin = s[_sage_const_1 ]
        yMax = n[_sage_const_1 ]
        err = max ([xMax - xMin, yMax - yMin]) * err
    # first underapproximation
    fi = [[n, w], [w, s], [s, e], [e, n]]
    # first overapproximation
    oi = [intersection_point (dn2d, n, dw2d, w), intersection_point (dw2d, w, ds2d, s), intersection_point (ds2d, s, de2d, e), intersection_point (de2d, e, dn2d, n)]
    # distances calculus
    di = []
    iMax = _sage_const_0 
    k = _sage_const_4 
    for i in range (_sage_const_0 , k) :
        di = di + [point_line_distance (fi[i], oi[i])]
        if (di[i] > di[iMax]) :
            iMax = i

    # 2) successive approximations
    while (di[iMax] > err) :
        #print 'k', k
        # refinement
        f = fi[iMax]
        p1 = f[_sage_const_0 ]
        p2 = f[_sage_const_1 ]
        d2d = normal_vector (p2 - p1)
        dnd = M2dnd * d2d
        pnd = extreme_point (A, b, dnd)
        p = Mnd2d * pnd
        q = intersection_point (normal_vector (p1 - oi[previous_i (iMax, k)]), p1, d2d, p)
        r = intersection_point (normal_vector (oi[next_i (iMax, k)] - p2), p2, d2d, p)
        # lists update
        fi = [fi[i] for i in range (_sage_const_0 , iMax)] + [[p1, p], [p, p2]] + [fi[i] for i in range (iMax + _sage_const_1 , k)]
        oi = [oi[i] for i in range (_sage_const_0 , iMax)] + [q, r] + [oi[i] for i in range (iMax + _sage_const_1 , k)]
        dq = point_line_distance ([p1, p], q)
        dr = point_line_distance ([p2, p], r)
        di = [di[i] for i in range (_sage_const_0 , iMax)] + [dq, dr] + [di[i] for i in range (iMax + _sage_const_1 , k)]
        k = k + _sage_const_1 
        # next iMax calculus
        iMax = _sage_const_0 
        for i in range (_sage_const_1 , k) :
            if (di[i] > di[iMax]) :
                iMax = i

    # result packaging and return
    ui = []
    for i in range (_sage_const_0 , len (fi)) :
        ui = ui + [fi[i][_sage_const_0 ]]
    return [oi, ui]



def extreme_point (A, b, d) :
    p = MixedIntegerLinearProgram (maximization = True)
    x = p.new_variable ()
    p.add_constraint (A*x <= b)
    f = _sage_const_0 
    for i in range (_sage_const_0 , d.length ()) :
        f = f + d[i]*x[i]
    p.set_objective (f)
    p.solve ()
    l = []
    for i in range (_sage_const_0 , d.length ()) :
        l = l + [p.get_values (x[i])]
    return vector (l)



def intersection_point (a1, p1, a2, p2) :
    M = Matrix ([a1, a2])
    if (M.determinant () == _sage_const_0 ) :
        return p2
    else :
        b = vector ([a1.dot_product(p1), a2.dot_product(p2)])
        return M.solve_right (b)





def point_line_distance (l, p) :
    a = l[_sage_const_0 ]
    b = l[_sage_const_1 ]
    n = normal_vector (b - a)
    if (n.norm () != _sage_const_0 ) :
        return abs (n.dot_product (p - a)) / n.norm ()
    else :
        return (p - a).norm ()





def normal_vector (v) :
    return vector ([v[_sage_const_1 ], -v[_sage_const_0 ]])



def next_i (i, n) :
    if (i == n-_sage_const_1 ) :
        return _sage_const_0 
    else :
        return i+_sage_const_1 


def previous_i (i, n) :
    if (i == _sage_const_0 ) :
        return n-_sage_const_1 
    else :
        return i-_sage_const_1 