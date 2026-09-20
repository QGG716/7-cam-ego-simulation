"""Fresh evaluated v3 mesh extraction; invisible or inactive PPE is excluded."""
import numpy as np

def extract(stage,prefix):
 from pxr import Usd,UsdGeom,UsdSkel,Vt
 skcache=UsdSkel.Cache();root=stage.GetPrimAtPath(prefix)
 skroots=[UsdSkel.Root(p) for p in Usd.PrimRange(root) if p.IsA(UsdSkel.Root)];skels=[UsdSkel.Skeleton(p) for p in Usd.PrimRange(root) if p.IsA(UsdSkel.Skeleton)]
 for sr in skroots:skcache.Populate(sr,Usd.PrimDefaultPredicate)
 if skels:
  sk=skels[0];trans=skcache.GetSkelQuery(sk).ComputeSkinningTransforms(0);sm=np.array(UsdGeom.Xformable(sk).ComputeLocalToWorldTransform(0))
 result={};verts={}
 for prim in Usd.PrimRange(root):
  if not prim.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(prim).ComputeVisibility()=='invisible':continue
  mesh=UsdGeom.Mesh(prim);pts=Vt.Vec3fArray(mesh.GetPointsAttr().Get());sq=skcache.GetSkinningQuery(prim)
  if sq and sq.HasJointInfluences():
   assert not sq.HasBlendShapes();assert sq.ComputeSkinnedPoints(trans,pts,0);m=sm
  else:m=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0))
  vertices=np.array(pts)@m[:3,:3]+m[3,:3];indices=mesh.GetFaceVertexIndicesAttr().Get();tri=[];offset=0
  for n in mesh.GetFaceVertexCountsAttr().Get():
   for k in range(1,n-1):tri.append([indices[offset],indices[offset+k],indices[offset+k+1]])
   offset+=n
  result[str(prim.GetPath())]=vertices[np.array(tri)];verts[str(prim.GetPath())]=vertices
 return result,verts
