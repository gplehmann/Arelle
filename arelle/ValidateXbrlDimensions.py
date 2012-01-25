'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from collections import defaultdict
from arelle import (UrlUtil, XbrlConst)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept

def loadDimensionDefaults(val):
    # load dimension defaults when required without performing validations
    val.modelXbrl.dimensionDefaultConcepts = {}
    val.modelXbrl.qnameDimensionDefaults = {}
    val.modelXbrl.qnameDimensionContextElement = {}
    for baseSetKey in val.modelXbrl.baseSets.keys():
        arcrole, ELR, linkqname, arcqname = baseSetKey
        if ELR and linkqname and arcqname and arcrole in (XbrlConst.all, XbrlConst.dimensionDefault):
            checkBaseSet(val, arcrole, ELR, val.modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname))
    val.modelXbrl.isDimensionsValidated = True

def checkBaseSet(val, arcrole, ELR, relsSet):
    # check hypercube-dimension relationships
    if arcrole == XbrlConst.hypercubeDimension:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if not fromConcept.isHypercubeItem:
                    val.modelXbrl.uuidError("b7c7abab9f8c49eeb1590bc8a5cac09e",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not toConcept.isDimensionItem:
                    val.modelXbrl.uuidError("2f4381bb37ab4b8dbd3a1a8eddeec658",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
    # check all, notAll relationships
    elif arcrole in (XbrlConst.all, XbrlConst.notAll):
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, hcRels in fromRelationships.items():
            for hasHcRel in hcRels:
                hcConcept = hasHcRel.toModelObject
                if priItemConcept is not None and hcConcept is not None:
                    if not priItemConcept.isPrimaryItem:
                        val.modelXbrl.uuidError("8b6cc069bbd04219ae4be357d1134ea5",
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole), 
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                    if not hcConcept.isHypercubeItem:
                        val.modelXbrl.uuidError("3cdd916e7e7841eea76d52f3a6e6f196",
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole), 
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                    hcContextElement = hasHcRel.contextElement
                    if hcContextElement not in ("segment","scenario"):
                        val.modelXbrl.uuidError("653a6b1291bd440eb0066eedf5c8b269",
                            modelObject=hasHcRel, arcroleType=os.path.basename(arcrole), 
                            source=priItemConcept.qname, target=hcConcept.qname, linkrole=ELR)
                        
                    # must check the cycles starting from hypercube ELR (primary item consec relationship
                    dimELR = hasHcRel.targetRole
                    if not dimELR:
                        dimELR = ELR
                    hcDimRels = val.modelXbrl.relationshipSet(
                         XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept)
                    for hcDimRel in hcDimRels:
                        dimConcept = hcDimRel.toModelObject
                        if dimConcept is not None:
                            if arcrole == XbrlConst.all:
                                val.modelXbrl.qnameDimensionContextElement[dimConcept.qname] = hcContextElement
                            domELR = hcDimRel.targetRole
                            if not domELR:
                                domELR = dimELR
                            dimDomRels = val.modelXbrl.relationshipSet(
                                 XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
                            cycle = xdtCycle(val, domainTargetRoles(val, domELR,dimDomRels), dimDomRels, {hcConcept,dimConcept})
                            if cycle is not None:
                                if cycle is not None:
                                    cycle.append(hcDimRel)
                                    path = str(hcConcept.qname) + " " + " - ".join(
                                        "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, rel.toModelObject.qname)
                                        for rel in reversed(cycle))
                                val.modelXbrl.uuidError("3c7ad3a77cb04347807c31657037d19e",
                                    modelObject=hcConcept, hypercube=hcConcept.qname, dimension=dimConcept.qname, linkrole=ELR, path=path)
                            cycle = drsPolymorphism(val, domELR, dimDomRels, drsPriItems(val, ELR, priItemConcept))
                            if cycle is not None:
                                if cycle is not None:
                                    cycle.append(hcDimRel)
                                    path = str(priItemConcept.qname) + " " + " - ".join(
                                        "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, rel.toModelObject.qname)
                                        for rel in reversed(cycle))
                                val.modelXbrl.uuidError("0c53093bbe6d4f58b4ed8a44cf05e2f2",
                                    modelObject=hcConcept, hypercube=hcConcept.qname, dimension=dimConcept.qname, linkrole=ELR, path=path)
    # check dimension-domain relationships
    elif arcrole == XbrlConst.dimensionDomain:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:   # none if failed to load
                if not fromConcept.isDimensionItem:
                    val.modelXbrl.uuidError("b566cbcd27234b8d9ea0b584d41dbe15",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                elif fromConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None:
                    val.modelXbrl.uuidError("adf46df8101048d885f9781d2cb0f95c",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not toConcept.isDomainMember:
                    val.modelXbrl.uuidError("e3e385e059394081b47923a31fea4659",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
    # check dimension-default relationships
    elif arcrole == XbrlConst.dimensionDefault:
        for modelRel in relsSet.modelRelationships:
            fromConcept = modelRel.fromModelObject
            toConcept = modelRel.toModelObject
            if fromConcept is not None and toConcept is not None:
                if not fromConcept.isDimensionItem:
                    val.modelXbrl.uuidError("efe630372dab4f42b76eb8558fcc1a96",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                elif fromConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"):
                    val.modelXbrl.uuidError("0fbf00730eba49768f2f2fb89af228c1",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if not toConcept.isDomainMember:
                    val.modelXbrl.uuidError("94fd677d637148a89146f4575c7a616a",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                if fromConcept in val.modelXbrl.dimensionDefaultConcepts and toConcept != val.modelXbrl.dimensionDefaultConcepts[fromConcept]:
                    val.modelXbrl.uuidError("9cc31e36973b40b9a412742aa0c710e0",
                        modelObject=modelRel, source=fromConcept.qname, target=toConcept.qname, 
                        target2=val.modelXbrl.dimensionDefaultConcepts[fromConcept].qname)
                else:
                    val.modelXbrl.dimensionDefaultConcepts[fromConcept] = toConcept
                    val.modelXbrl.qnameDimensionDefaults[fromConcept.qname] = toConcept.qname

    # check for primary item cycles
    elif arcrole == XbrlConst.domainMember:
        fromRelationships = relsSet.fromModelObjects()
        for priItemConcept, rels in fromRelationships.items():
                for domMbrRel in rels:
                    toConcept = domMbrRel.toModelObject
                    if toConcept is not None:
                        if not priItemConcept.isDomainMember:
                            val.modelXbrl.uuidError("03d3b50e85454a75843a62ac5bc0e329",
                                modelObject=domMbrRel, source=priItemConcept.qname, target=toConcept.qname, linkrole=ELR)
                        if not toConcept.isDomainMember:
                            val.modelXbrl.uuidError("a577dae36ab2421287f7c8f010dfcc09",
                                modelObject=domMbrRel, source=priItemConcept.qname, target=toConcept.qname, linkrole=ELR)

def domainTargetRoles(val, fromELR, rels, fromConcepts=None, ELRs=None):
    if fromConcepts is None:
        fromConcepts = set()
    if not ELRs:
        ELRs = {fromELR}
    for rel in rels:
        relTo = rel.toModelObject
        if relTo not in fromConcepts:
            fromConcepts.add(relTo)
            toELR = rel.targetRole
            if toELR:
                ELRs.add(toELR)
            else:
                toELR = fromELR
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)
            domainTargetRoles(val, toELR, domMbrRels, fromConcepts, ELRs)
            fromConcepts.discard(relTo)
    return ELRs

def xdtCycle(val, ELRs, rels, fromConcepts):
    for rel in rels:
        relTo = rel.toModelObject
        if rel.isUsable and relTo in fromConcepts: # don't think we want this?? and toELR == drsELR: #forms a directed cycle
            return [rel,]
        fromConcepts.add(relTo)
        for ELR in ELRs: 
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(relTo)
            foundCycle = xdtCycle(val, ELRs, domMbrRels, fromConcepts)
            if foundCycle is not None:
                foundCycle.append(rel)
                return foundCycle
        fromConcepts.discard(relTo)
    return None

def drsPriItems(val, fromELR, fromPriItem, priItems=None):
    if priItems is None:
        priItems = {fromPriItem}
    for rel in  val.modelXbrl.relationshipSet(XbrlConst.domainMember, fromELR).fromModelObject(fromPriItem):
        toPriItem = rel.toModelObject
        if toPriItem not in priItems:
            if rel.isUsable:
                priItems.add(toPriItem)
            toELR = rel.targetRole
            drsPriItems(val, toELR if toELR else fromELR, toPriItem, priItems)
    return priItems

def drsPolymorphism(val, fromELR, rels, priItems, visitedMbrs=None):
    if visitedMbrs is None:
        visitedMbrs = set()
    for rel in rels:
        relTo = rel.toModelObject
        toELR = rel.targetRole
        if not toELR:
            toELR = fromELR
        if rel.isUsable and relTo in priItems: # don't think we want this?? and toELR == drsELR: #forms a directed cycle
            return [rel,]
        if relTo not in visitedMbrs:
            visitedMbrs.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)
            foundCycle = drsPolymorphism(val, toELR, domMbrRels, priItems, visitedMbrs)
            if foundCycle is not None:
                foundCycle.append(rel)
                return foundCycle
            visitedMbrs.discard(relTo)
    return None

def checkConcept(val, concept):
    if concept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"):
        if concept.isDimensionItem:
            typedDomainElement = concept.typedDomainElement
            if typedDomainElement is None:
                url, id = UrlUtil.splitDecodeFragment(concept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef"))
                if len(id) == 0:
                    val.modelXbrl.uuidError("386556f8a2f94426848059cfc27856e8",
                        modelObject=concept, concept=concept.qname)
                else:
                    val.modelXbrl.uuidError("406fe632e60d442c9fc8915354b79b94",
                        modelObject=concept, concept=concept.qname)
            elif not isinstance(typedDomainElement, ModelConcept) or \
                        not typedDomainElement.isGlobalDeclaration or \
                        typedDomainElement.abstract == "true":
                val.modelXbrl.uuidError("ae6d430da76d41c3855c3594a4787f7e",
                        modelObject=concept, concept=concept.qname)
        else:
            val.modelXbrl.uuidError("be1eb6f6e8ae44438db39571bc4c75b0",
                modelObject=concept, concept=concept.qname)

def checkContext(val, cntx):
    # check errorDimensions of context
    for modelDimValues in (cntx.segDimValues.values(), cntx.scenDimValues.values(), cntx.errorDimValues):
        for modelDimValue in modelDimValues:
            dimensionConcept = modelDimValue.dimension
            if dimensionConcept is None or \
                not dimensionConcept.isDimensionItem or \
                modelDimValue.isTyped != (dimensionConcept.get("{http://xbrl.org/2005/xbrldt}typedDomainRef") is not None):
                val.modelXbrl.uuidError("ba6773a1384e462990260a0aaf6a4810" if modelDimValue.isTyped else "b025b75e23104a54ab453f84f0f3bb0a",
                    modelObject=modelDimValue, contextID=cntx.id, 
                    dimension=modelDimValue.prefixedName, value=modelDimValue.dimensionQname)
            elif modelDimValue.isExplicit:
                memberConcept = modelDimValue.member
                if memberConcept is None or not memberConcept.isGlobalDeclaration:
                    val.modelXbrl.uuidError("169e4f3b1c834a03b2a88265cc14c919",
                        modelObject=modelDimValue, contextID=cntx.id, 
                        dimension=modelDimValue.dimensionQname, value=modelDimValue.memberQname)
                if val.modelXbrl.dimensionDefaultConcepts.get(dimensionConcept) == memberConcept:
                    val.modelXbrl.uuidError("2e33405adc6a44c9ade30034878e0f71",
                        modelObject=modelDimValue, contextID=cntx.id, 
                        dimension=modelDimValue.dimensionQname, value=modelDimValue.memberQname)
            elif modelDimValue.isTyped:
                typedDomainConcept = dimensionConcept.typedDomainElement
                problem = _("missing content")                
                for element in modelDimValue.getchildren():
                    if isinstance(element,ModelObject):
                        if problem is None:
                            problem = _("multiple contents")
                        elif element.localName != typedDomainConcept.name or \
                            element.namespaceURI != typedDomainConcept.qname.namespaceURI:
                            problem = _("wrong content {0}").format(element.prefixedName)
                        else:
                            problem = None
                if problem:
                    val.modelXbrl.uuidError("3ba9b9bc3406497486ba1a67506b0ac8",
                        modelObject=modelDimValue, contextID=cntx.id, 
                        dimension=modelDimValue.dimensionQname, error=problem)

    for modelDimValue in cntx.errorDimValues:
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept is not None \
           and (dimensionConcept in cntx.segDimValues or dimensionConcept in cntx.scenDimValues):
            val.modelXbrl.uuidError("4010c7c5c36f4781bdcb6f0e1ac93d00",
                modelObject=modelDimValue, contextID=cntx.id, dimension=modelDimValue.dimensionQname)
    # decision by WG that dimensions in both seg & scen is also a duplication
    for modelDimValue in cntx.segDimValues.values():
        dimensionConcept = modelDimValue.dimension
        if dimensionConcept is not None and dimensionConcept in cntx.scenDimValues:
            val.modelXbrl.uuidError("4010c7c5c36f4781bdcb6f0e1ac93d00",
                modelObject=modelDimValue, contextID=cntx.id, dimension=modelDimValue.dimensionQname)
            
def checkFact(val, f):
    if not isFactDimensionallyValid(val, f):
        val.modelXbrl.uuidError("d16726e0c6824de6abbf996346afd566",
            modelObject=f, fact=f.concept.qname, contextID=f.context.id)

def isFactDimensionallyValid(val, f):
    hasElrHc = False
    for ELR, hcRels in priItemElrHcRels(val, f.concept).items():
        hasElrHc = True
        if checkFactElrHcs(val, f, ELR, hcRels):
            return True # meets hypercubes in this ELR
        
    if hasElrHc:
        # no ELR hypercubes fully met
        return False
    return True
    
def priItemElrHcRels(val, priItem, ELR=None, elrHcRels=None):
    if elrHcRels is None:
        elrHcRels = defaultdict(list)
    # add has hypercube relationships for ELR
    for arcrole in (XbrlConst.all, XbrlConst.notAll):
        for hasHcRel in val.modelXbrl.relationshipSet(arcrole,ELR).fromModelObject(priItem):
            elrHcRels[hasHcRel.linkrole].append(hasHcRel)
    # check inherited ELRs
    for domMbrRel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).toModelObject(priItem):
        toELR = domMbrRel.targetRole
        relLinkrole = domMbrRel.linkrole
        if toELR is None:
            toELR = relLinkrole
        if ELR is None or ELR == toELR:
            priItemElrHcRels(val, domMbrRel.fromModelObject, relLinkrole, elrHcRels)
    return elrHcRels

NOT_FOUND = 0
MEMBER_USABLE = 1
MEMBER_NOT_USABLE = 2

def checkFactElrHcs(val, f, ELR, hcRels):
    context = f.context
    elrValid = True # start assuming ELR is valid
    
    for hasHcRel in hcRels:
        hcConcept = hasHcRel.toModelObject
        hcIsClosed = hasHcRel.isClosed
        hcContextElement = hasHcRel.contextElement
        hcNegating = hasHcRel.arcrole == XbrlConst.notAll
        modelDimValues = context.dimValues(hcContextElement)
        contextElementDimSet = set(modelDimValues.keys())
        modelNonDimValues = context.nonDimValues(hcContextElement)
        hcValid = True
        
        # if closed and any nonDim values, hc invalid
        if hcIsClosed and len(modelNonDimValues) > 0:
            hcValid = False
        else:
            dimELR = hasHcRel.targetRole
            if dimELR is None:
                dimELR = ELR
            for hcDimRel in val.modelXbrl.relationshipSet(
                                XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):
                dimConcept = hcDimRel.toModelObject
                domELR = hcDimRel.targetRole
                if domELR is None:
                    domELR = dimELR
                if dimConcept in modelDimValues:
                    memModelDimension = modelDimValues[dimConcept]
                    contextElementDimSet.discard(dimConcept)
                    memConcept = memModelDimension.member
                elif dimConcept in val.modelXbrl.dimensionDefaultConcepts:
                    memConcept = val.modelXbrl.dimensionDefaultConcepts[dimConcept]
                else:
                    hcValid = False
                    continue
                if not dimConcept.isTypedDimension:
                    if dimensionMemberState(val, dimConcept, memConcept, domELR) != MEMBER_USABLE:
                        hcValid = False 
        if hcIsClosed and len(contextElementDimSet) > 0:
            hcValid = False # has extra stuff in the context element
        if hcNegating:
            hcValid = not hcValid
        if not hcValid:
            elrValid = False
    return elrValid
                            
def dimensionMemberState(val, dimConcept, memConcept, domELR):
    try:
        dimensionMemberStates = val.dimensionMemberStates
    except AttributeError:
        dimensionMemberStates = val.dimensionMemberStates = {}
    key = (dimConcept, memConcept, domELR)
    try:
        return dimensionMemberStates[key]
    except KeyError:
        dimDomRels = val.modelXbrl.relationshipSet(
                        XbrlConst.dimensionDomain, domELR).fromModelObject(dimConcept)
        state = memberStateInDomain(val, memConcept, dimDomRels, domELR)
        dimensionMemberStates[key] = state
        return state

def memberStateInDomain(val, memConcept, rels, ELR, fromConcepts=None):
    foundState = NOT_FOUND
    if fromConcepts is None:
        fromConcepts = set()
    for rel in rels:
        toConcept = rel.toModelObject
        if toConcept == memConcept:
            foundState = max(foundState, 
                             MEMBER_USABLE if rel.isUsable else MEMBER_NOT_USABLE)
        if toConcept not in fromConcepts:
            fromConcepts.add(toConcept)
        toELR = rel.targetRole
        if toELR is None:
            toELR = ELR
        domMbrRels = val.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(toConcept)
        foundState = max(foundState,
                         memberStateInDomain(val, memConcept, domMbrRels, toELR, fromConcepts))
        fromConcepts.discard(toConcept)
    return foundState

# check a single dimension value for primary item (not the complete set of dimension values)
def checkPriItemDimValueValidity(val, priItemConcept, dimConcept, memConcept):
    if priItemConcept and dimConcept and memConcept:
        for ELR, hcRels in priItemElrHcRels(val, priItemConcept).items():
            if checkPriItemDimValueElrHcs(val, priItemConcept, dimConcept, memConcept, ELR, hcRels):
                return True
    return False

def checkPriItemDimValueElrHcs(val, priItemConcept, matchDim, matchMem, ELR, hcRels):
    for hasHcRel in hcRels:
        hcConcept = hasHcRel.toModelObject
        hcIsClosed = hasHcRel.isClosed
        hcNegating = hasHcRel.arcrole == XbrlConst.notAll
        
        dimELR = hasHcRel.targetRole
        if dimELR is None:
            dimELR = ELR
        for hcDimRel in val.modelXbrl.relationshipSet(
                            XbrlConst.hypercubeDimension, dimELR).fromModelObject(hcConcept):
            dimConcept = hcDimRel.toModelObject
            if dimConcept != matchDim:
                continue
            domELR = hcDimRel.targetRole
            if domELR is None:
                domELR = dimELR
            if dimensionMemberState(val, dimConcept, matchMem, domELR) != MEMBER_USABLE:
                return hcNegating # true if all, false if not all
        if hcIsClosed:
            return False # has extra stuff in the context element
        if hcNegating:
            return True
    return True
