"""Triangle-level fit audit for evaluated meshes; metres throughout."""
import numpy as np

def segments_hit_triangles(origins, ends, tris, eps=1e-9):
    # Broadcast equally-sized segment/triangle pairs; inclusive boundary hits.
    d=ends-origins; a,b,c=np.moveaxis(tris,1,0);e1=b-a;e2=c-a
    h=np.cross(d,e2);det=np.einsum('ij,ij->i',e1,h)
    threshold=1e-12*np.linalg.norm(d,axis=1)*np.linalg.norm(e1,axis=1)*np.linalg.norm(e2,axis=1)
    inv=np.divide(1,det,out=np.zeros_like(det),where=abs(det)>threshold)
    s=origins-a;u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1)
    v=inv*np.einsum('ij,ij->i',d,q);t=inv*np.einsum('ij,ij->i',e2,q)
    return (abs(det)>threshold)&(u>=-eps)&(v>=-eps)&(u+v<=1+eps)&(t>=-eps)&(t<=1+eps)

def surface_crossings(a,b):
    """All triangle pairs with intersecting AABBs, testing edges in both directions.
    Coplanar pairs separately tested by 2-D convex SAT. No centerline proxy.
    """
    blo=b.min(1);bhi=b.max(1);pairs=[];coplanar=0
    for i,tri in enumerate(a):
        ids=np.flatnonzero(np.all(bhi>=tri.min(0)-1e-9,axis=1)&np.all(blo<=tri.max(0)+1e-9,axis=1))
        if not len(ids):continue
        bt=b[ids];at=np.broadcast_to(tri,bt.shape);hit=np.zeros(len(ids),bool)
        for k in range(3):
            hit|=segments_hit_triangles(at[:,k],at[:,(k+1)%3],bt)
            hit|=segments_hit_triangles(bt[:,k],bt[:,(k+1)%3],at)
        n=np.cross(tri[1]-tri[0],tri[2]-tri[0]);norm=np.linalg.norm(n)
        if norm>1e-12:
            n/=norm;co=np.max(abs((bt-tri[0])@n),axis=1)<1e-9
            for j in np.flatnonzero(co & ~hit):
                axes=np.concatenate([np.cross(np.roll(tri,-1,axis=0)-tri,n),np.cross(np.roll(bt[j],-1,axis=0)-bt[j],n)])
                pa=tri@axes.T;pb=bt[j]@axes.T
                if not np.any((pa.max(0)<pb.min(0)-1e-12)|(pb.max(0)<pa.min(0)-1e-12)):hit[j]=True;coplanar+=1
        pairs.extend((i,int(k)) for k in ids[hit])
    return pairs,coplanar

def inside(points,tris):
    """Odd/even closed-surface classification, de-duplicated coincident crossings."""
    direction=np.array([1.,.1732050807,.0710678119]);direction/=np.linalg.norm(direction)
    a,b,c=np.moveaxis(tris,1,0);e1=b-a;e2=c-a;h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
    inv=np.divide(1,det,out=np.zeros_like(det),where=abs(det)>1e-12);result=[]
    for point in points:
        s=point-a;u=inv*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=inv*(q@direction);t=inv*np.einsum('ij,ij->i',e2,q)
        hits=t[(abs(det)>1e-12)&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-7)]
        result.append(len(np.unique(np.round(hits,7)))%2==1)
    return np.array(result)

def point_triangle_distance(points,tris):
    """Distance for broadcast corresponding pairs of points and triangles."""
    a,b,c=np.moveaxis(tris,1,0);ab=b-a;ac=c-a;ap=points-a
    n=np.cross(ab,ac);nn=np.einsum('ij,ij->i',n,n);dp=np.einsum('ij,ij->i',ap,n)
    proj=points-n*np.divide(dp,nn,out=np.zeros_like(dp),where=nn>1e-24)[:,None]
    v=proj-a;aa=np.einsum('ij,ij->i',ab,ab);bb=np.einsum('ij,ij->i',ab,ac);cc=np.einsum('ij,ij->i',ac,ac)
    av=np.einsum('ij,ij->i',v,ab);cv=np.einsum('ij,ij->i',v,ac);den=aa*cc-bb*bb
    u=np.divide(cc*av-bb*cv,den,out=np.full_like(den,-1),where=abs(den)>1e-24)
    w=np.divide(aa*cv-bb*av,den,out=np.full_like(den,-1),where=abs(den)>1e-24)
    dist=np.where((u>=0)&(w>=0)&(u+w<=1),np.divide(dp*dp,nn,out=np.full_like(nn,np.inf),where=nn>1e-24),np.inf)
    for start,end in [(a,b),(b,c),(c,a)]:
        e=end-start;ee=np.einsum('ij,ij->i',e,e);t=np.clip(np.divide(np.einsum('ij,ij->i',points-start,e),ee,out=np.zeros_like(ee),where=ee>1e-24),0,1)
        dist=np.minimum(dist,np.sum((points-start-e*t[:,None])**2,axis=1))
    return np.sqrt(dist)

def sampled_clearance(a,b,spacing=.002):
    """Surface sample spacing <= spacing on each triangle, exact nearest triangle
    distances selected by a distance-safe AABB bound. Returns sampled minimum only.
    """
    from scipy.spatial import cKDTree
    vertices=b.reshape(-1,3);tree=cKDTree(vertices);lo=b.min(1);hi=b.max(1);best=np.inf;count=0
    for tri in a:
        n=max(1,int(np.ceil(max(np.linalg.norm(tri[1]-tri[0]),np.linalg.norm(tri[2]-tri[0]),np.linalg.norm(tri[2]-tri[1]))/spacing)))
        pts=np.array([tri[0]+(tri[1]-tri[0])*i/n+(tri[2]-tri[0])*j/n for i in range(n+1) for j in range(n+1-i)])
        ds,_=tree.query(pts);count+=len(pts)
        for p,d in zip(pts,ds):
            # Only points potentially improving current sampled minimum need refinement.
            bound=min(d,best);delta=np.maximum(np.maximum(lo-p,p-hi),0);ids=np.flatnonzero(np.einsum('ij,ij->i',delta,delta)<=bound*bound+1e-16)
            if len(ids):best=min(best,float(point_triangle_distance(np.broadcast_to(p,(len(ids),3)),b[ids]).min()))
    return best,count

def audit(objects,body):
    allbody=np.concatenate(list(body.values()));rows=[]
    for name,tri in objects.items():
        near=allbody[np.all(allbody.max(1)>=tri.min((0,1))-.025,axis=1)&np.all(allbody.min(1)<=tri.max((0,1))+.025,axis=1)]
        if not len(near):rows.append(dict(path=name,triangle_crossings=0,minimum_sampled_gap_m=None));continue
        pairs,co=surface_crossings(tri,near)
        # Full closed rig solid: human vertices inside it catch containment too.
        pts=np.unique(near.reshape(-1,3),axis=0);pts=pts[np.all(pts>=tri.min((0,1)),axis=1)&np.all(pts<=tri.max((0,1)),axis=1)]
        contained=int(inside(pts,tri).sum()) if len(pts) else 0
        gap,n=sampled_clearance(tri,near)
        rows.append(dict(path=name,triangles=len(tri),candidate_body_triangles=len(near),triangle_crossings=len(pairs),coplanar_contacts=co,human_vertices_inside_solid=contained,minimum_sampled_gap_m=gap,distance_samples=n))
    return rows
