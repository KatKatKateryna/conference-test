
from copy import copy

import numpy as np
from specklepy.objects.geometry import Point

RESULT_BRANCH = "automate"
COLOR_ROAD = (255<<24) + (50<<16) + (50<<8) + 50 # argb
COLOR_BLD = (255<<24) + (230<<16) + (230<<8) + 230 # argb
COLOR_VISIBILITY = (255<<24) + (255<<16) + (10<<8) + 10 # argb

def findMeshesNearby(cleanPts: list[Point]) -> list[Point]:
    # add indices of neighbouring meshes
    mesh_nearby = []
    for pt in cleanPts:
        meshIds = []
        all_mesh_dist = []
        all_mesh_ids = []
        for p in cleanPts:
            distance = np.sqrt(np.sum(( np.array([p.x,p.y,p.z]) -np.array([pt.x,pt.y,pt.z]))**2, axis=0))
            if distance ==0: continue
            all_mesh_dist.append(distance)
            all_mesh_ids.append(p.meshId)
        minDist = min(all_mesh_dist)
        meshIds = [ m for i,m in enumerate(all_mesh_ids) if all_mesh_dist[i] < minDist*2 ]
        mesh_nearby.append(list(set(meshIds)))
    return mesh_nearby

def sortPtsByMesh(cleanPts: list[Point]) -> list[Point]:
    ptsGroups: list[list[np.array]] = []
    
    usedMeshIds = []
    for pt in cleanPts:
        if pt.meshId in usedMeshIds: continue

        meshId = pt.meshId
        morePts = [ p for p in cleanPts if p.meshId == meshId]
        ptsGroups.append(morePts)
        usedMeshIds.append(meshId)

    return ptsGroups

def cleanPtsList(pt_origin, all_pts, usedVectors):
    
    cleanPts = []
    checkedPtIds = []
    p1 = np.array(pt_origin)
    
    for i, pt in enumerate(all_pts):
        if i in checkedPtIds: continue
        
        vectorId = pt.vectorId
        meshId = pt.meshId
        vectorCount = usedVectors[pt.vectorId]
        if vectorCount>1:
            pack = [ [np.array([p.x, p.y, p.z]),x,p.meshId]  for x,p in enumerate(all_pts) if p.vectorId == vectorId]
            competingPts = [ x[0] for x in pack]
            competingPtIds = [ x[1] for x in pack]
            competingPtMeshIds = [ x[2] for x in pack]

            checkedPtIds.extend(competingPtIds) # remove points from this vector from further search

            distance = None
            finalPt = None
            for x, p2 in enumerate(competingPts):
                
                squared_dist = np.sum((p1-p2)**2, axis=0)
                dist = np.sqrt(squared_dist)
                if (distance is None or dist < distance) and dist > 0.00001: 
                    distance=dist
                    finalPt = Point.from_list([p2[0], p2[1], p2[2]])
                    finalPt.meshId = competingPtMeshIds[x]
                    finalPt.vectorId = vectorId
                    finalPt.distance = dist
            if distance is not None and finalPt is not None:
                cleanPts.append(finalPt)
                
        else:
            p2 = np.array([pt.x, pt.y, pt.z])
            squared_dist = np.sum((p1-p2)**2, axis=0)
            dist = np.sqrt(squared_dist)
            if dist > 0.00001:
                cleanPts.append(pt)
    return cleanPts

def cleanString(text: str) -> str:
    symbols = r"/[^\d.-]/g, ''"
    new_text = text
    for s in symbols:
        new_text = new_text.split(s)[0]#.replace(s, "")
    return new_text

def fillList(vals: list, lsts: list) -> list[list]:
    if len(vals)>1: 
        lsts.append([])
    else: return

    for i, v in enumerate(vals):
        if v not in lsts[len(lsts)-1]: lsts[len(lsts)-1].append(v)
        else: 
            if len(lsts[len(lsts)-1])<=1: lsts.pop(len(lsts)-1)
            vals = copy(vals[i-1:])
            fillList(vals, lsts)
    return lsts 
    