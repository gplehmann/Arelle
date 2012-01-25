'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from collections import defaultdict
from arelle import XbrlConst

def checkDimensions(val, drsELRs):
    
    fromConceptELRs = defaultdict(set)
    hypercubes = set()
    hypercubesInLinkrole = defaultdict(set)
    hypercubeDRSDimensions = defaultdict(dict)
    for ELR in drsELRs:
        domainMemberRelationshipSet = val.modelXbrl.relationshipSet( XbrlConst.domainMember, ELR)
                            
        # check Hypercubes in ELR, accumulate list of primary items
        positiveAxisTableSources = defaultdict(set)
        positiveHypercubes = set()
        primaryItems = set()
        for hasHypercubeArcrole in (XbrlConst.all, XbrlConst.notAll):
            hasHypercubeRelationships = val.modelXbrl.relationshipSet(
                             hasHypercubeArcrole, ELR).fromModelObjects()
            for hasHcRels in hasHypercubeRelationships.values():
                numberOfHCsPerSourceConcept = 0
                for hasHcRel in hasHcRels:
                    sourceConcept = hasHcRel.fromModelObject
                    primaryItems.add(sourceConcept)
                    hc = hasHcRel.toModelObject
                    hypercubes.add(hc)
                    if hasHypercubeArcrole == XbrlConst.all:
                        positiveHypercubes.add(hc)
                        if not hasHcRel.isClosed:
                            val.modelXbrl.uuidError("86cb2ef17c1e4d11b9d0a3639d6a3709",
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                    elif hasHypercubeArcrole == XbrlConst.notAll:
                        if hasHcRel.isClosed:
                            val.modelXbrl.uuidError("ab10ad519bec42dcbe9aae3871afc4bf",
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                        if hc in positiveHypercubes:
                            val.modelXbrl.uuidError("b08b6d01e8ec4fc3a8c316f8d4fc114f",
                                modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                    numberOfHCsPerSourceConcept += 1
                    dimELR = hasHcRel.targetRole
                    dimTargetRequired = (dimELR is not None)
                    if not dimELR:
                        dimELR = ELR
                    hypercubesInLinkrole[dimELR].add(hc) # this is the elr containing the HC-dim relations
                    hcDimRels = val.modelXbrl.relationshipSet(
                             XbrlConst.hypercubeDimension, dimELR).fromModelObject(hc)
                    if dimTargetRequired and len(hcDimRels) == 0:
                        val.modelXbrl.uuidError("36a370ff033a409eb12c3034dcaf41f0",
                            modelObject=hasHcRel, hypercube=hc.qname, linkrole=ELR)
                    for hcDimRel in hcDimRels:
                        dim = hcDimRel.toModelObject
                        domELR = hcDimRel.targetRole
                        domTargetRequired = (domELR is not None)
                        if not domELR:
                            domELR = dimELR
                            if val.validateSBRNL:
                                val.modelXbrl.uuidError("327a0e7bfeae4a4881f29bb93691eaa0",
                                    modelObject=hcDimRel, hypercube=hc.qname, linkrole=ELR, dimension=dim.qname)
                        else:
                            if dim.isTypedDimension and val.validateSBRNL:
                                val.modelXbrl.uuidError("7682199616b442f59a155fff2f293e78",
                                    modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR)
                        if hasHypercubeArcrole == XbrlConst.all:
                            positiveAxisTableSources[dim].add(sourceConcept)
                            try:
                                hcDRSdims = hypercubeDRSDimensions[hc][domELR]
                            except KeyError:
                                hcDRSdims = set()
                                hypercubeDRSDimensions[hc][domELR] = hcDRSdims
                            hcDRSdims.add(dim)
                        elif hasHypercubeArcrole == XbrlConst.notAll and \
                             (dim not in positiveAxisTableSources or \
                              not commonAncestor(domainMemberRelationshipSet,
                                              sourceConcept, positiveAxisTableSources[dim])):
                            val.modelXbrl.uuidError("db6d376d96274f3d8943c0b511bcef4d",
                                 modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR)
                        dimDomRels = val.modelXbrl.relationshipSet(
                             XbrlConst.dimensionDomain, domELR).fromModelObject(dim)   
                        if domTargetRequired and len(dimDomRels) == 0:
                            val.modelXbrl.uuidError("60311851aee24a1eabbaacc317cb4092",
                                modelObject=hcDimRel, dimension=dim.qname, linkrole=ELR)
                        if val.validateEFMorGFM:
                            # flatten DRS member relationsihps in ELR for undirected cycle detection
                            drsRelsFrom = defaultdict(list)
                            drsRelsTo = defaultdict(list)
                            getDrsRels(val, domELR, dimDomRels, ELR, drsRelsFrom, drsRelsTo)
                            # check for cycles
                            fromConceptELRs[hc].add(dimELR)
                            fromConceptELRs[dim].add(domELR)
                            cycleCausingConcept = undirectedFwdCycle(val, domELR, dimDomRels, ELR, drsRelsFrom, drsRelsTo, fromConceptELRs)
                            if cycleCausingConcept is not None:
                                cycleCausingConcept.append(hcDimRel)
                                val.modelXbrl.uuidError("1bc0e3062b4d443b8a6abfeb3907ca2e",
                                    modelObject=hcDimRel, linkrole=ELR, hypercube=hc.qname, dimension=dim.qname, path=cyclePath(hc,cycleCausingConcept))
                            fromConceptELRs.clear()
                        elif val.validateSBRNL:
                            checkSBRNLMembers(val, hc, dim, domELR, dimDomRels, ELR, True)
                if hasHypercubeArcrole == XbrlConst.all and numberOfHCsPerSourceConcept > 1:
                    val.modelXbrl.uuidError("086215ce9d1141c4bc6c2236f7627fcf",
                        modelObject=sourceConcept, 
                        hypercubeCount=numberOfHCsPerSourceConcept, linkrole=ELR, concept=sourceConcept.qname)
                    
        # check for primary item dimension-member graph undirected cycles
        fromRelationships = domainMemberRelationshipSet.fromModelObjects()
        for relFrom, rels in fromRelationships.items():
            if relFrom in primaryItems:
                drsRelsFrom = defaultdict(list)
                drsRelsTo = defaultdict(list)
                getDrsRels(val, ELR, rels, ELR, drsRelsFrom, drsRelsTo)
                fromConceptELRs[relFrom].add(ELR)
                cycleCausingConcept = undirectedFwdCycle(val, ELR, rels, ELR, drsRelsFrom, drsRelsTo, fromConceptELRs)
                if cycleCausingConcept is not None:
                    val.modelXbrl.uuidError("799383b05187485da300a382b2aa9013",
                        modelObject=relFrom, linkrole=ELR, conceptFrom=relFrom.qname, path=cyclePath(relFrom, cycleCausingConcept))
                fromConceptELRs.clear()
            for rel in rels:
                fromMbr = rel.fromModelObject
                toMbr = rel.toModelObject
                toELR = rel.targetRole
                if toELR and len(
                    val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(toMbr)) == 0:
                    val.modelXbrl.uuidError("929944d431f340e3921885685420a638",
                        modelObject=rel, concept=fromMbr.qname, linkrole=ELR)
                    
    if val.validateSBRNL:
        # check hypercubes for unique set of members
        for hc in hypercubes:
            for priHcRel in val.modelXbrl.relationshipSet(XbrlConst.all).toModelObject(hc):
                priItem = priHcRel.fromModelObject
                ELR = priHcRel.linkrole
                checkSBRNLMembers(val, hc, priItem, ELR, 
                                  val.modelXbrl.relationshipSet(XbrlConst.domainMember, ELR).fromModelObject(priItem), 
                                  ELR, False)
                if priHcRel.contextElement == 'segment':  
                    val.modelXbrl.uuidError("8b78b9abdfd94703a7bd27c9d79b7703",
                        modelObject=priHcRel, linkrole=ELR, hypercube=hc.qname)
        for notAllRel in val.modelXbrl.relationshipSet(XbrlConst.notAll).modelRelationships:
            val.modelXbrl.uuidError("fc7bff4d95c44a61922f9911bbc18721",
                modelObject=val.modelXbrl, primaryItem=notAllRel.fromModelObject.qname, linkrole=notAllRel.linkrole, hypercube=notAllRel.toModelObject.qname)
        for ELR, hypercubes in hypercubesInLinkrole.items():
            '''removed RH 2011-12-06
            for modelRel in val.modelXbrl.relationshipSet("XBRL-dimensions", ELR).modelRelationships:
                if modelRel.fromModelObject != hc:
                    val.modelXbrl.error("SBR.NL.2.3.5.03",
                        _("ELR role %(linkrole)s, is not dedicated to %(hypercube)s, but also has %(otherQname)s"),
                        modelObject=val.modelXbrl, linkrole=ELR, hypercube=hc.qname, otherQname=modelRel.fromModelObject.qname)
            '''
            for hc in hypercubes:  # only one member
                for arcrole in (XbrlConst.parentChild, "XBRL-dimensions"):
                    for modelRel in val.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                        if modelRel.fromModelObject != hc and modelRel.toModelObject != hc:
                            val.modelXbrl.uuidError("9b312ec256bf4a5a93ea7d4af37705b4",
                                modelObject=modelRel, linkrole=ELR, hypercube=hc.qname, concept=modelRel.fromModelObject.qname)
        domainsInLinkrole = defaultdict(set)
        dimDomsByLinkrole = defaultdict(set)
        for rel in val.modelXbrl.relationshipSet(XbrlConst.dimensionDomain).modelRelationships:
            relFrom = rel.fromModelObject
            relTo = rel.toModelObject
            domainsInLinkrole[rel.targetRole].add(relFrom)
            dimDomsByLinkrole[(rel.linkrole,relFrom)].add(relTo)
            if rel.isUsable and val.modelXbrl.relationshipSet(XbrlConst.domainMember, rel.targetRole).fromModelObject(relTo):
                val.modelXbrl.uuidError("8b51ab9369984febb0f19f7eb6250df5",
                    modelObject=rel, dimension=relFrom.qname, linkrole=rel.linkrole, domain=relTo.qname)
            if not relTo.isAbstract:
                val.modelXbrl.uuidError("0aa2585b4dd840929213d62c126029d2",
                    modelObject=rel, dimension=relFrom.qname, linkrole=rel.linkrole, domain=relTo.qname)
            if relTo.substitutionGroupQname.localName not in ("domainItem","domainMemberItem"):
                val.modelXbrl.uuidError("fcc8dd3e3f6341adb1ff346df66e2108",
                    modelObject=rel, domain=relTo.qname, linkrole=rel.linkrole, dimension=relFrom.qname)
            if not rel.targetRole and relTo.substitutionGroupQname.localName == "domainItem":
                val.modelXbrl.uuidError("4459428734c843eca04afcf03440c584",
                    modelObject=rel, dimension=relFrom.qname, linkrole=rel.linkrole)
        for linkrole, domains in domainsInLinkrole.items():
            if linkrole and len(domains) > 1:
                val.modelXbrl.uuidError("0707c89590e145748d5224816f450963",
                    modelObject=val.modelXbrl, linkrole=linkrole, domains=", ".join([str(dom.qname) for dom in domains]))
        del domainsInLinkrole   # dereference
        linkrolesByDimDoms = defaultdict(set)
        for linkroleDim, doms in dimDomsByLinkrole.items():
            linkrole, dim = linkroleDim
            linkrolesByDimDoms[(dim,tuple(doms))].add(linkrole)
        for dimDoms, linkroles in linkrolesByDimDoms.items():
            if len(linkroles) > 1:
                val.modelXbrl.uuidError("37e15d569c914f9f84c139a72775d81f",
                    modelObject=val.modelXbrl, dimension=dimDoms[0].qname, linkroles=', '.join(l for l in linkroles))
        del dimDomsByLinkrole, linkrolesByDimDoms
        for rel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).modelRelationships:
            if val.modelXbrl.relationshipSet(XbrlConst.domainMember, rel.targetRole).fromModelObject(rel.toModelObject):
                val.modelXbrl.uuidError("e188bccd08d441a38e4ef4e212f32b81",
                    modelObject=rel, member=rel.toModelObject.qname, linkrole=rel.linkrole)
        for rel in val.modelXbrl.relationshipSet(XbrlConst.domainMember).modelRelationships:
            relFrom = rel.fromModelObject
            relTo = rel.toModelObject
            # avoid primary item relationships in these tests
            if relFrom.substitutionGroupQname.localName == "domainItem":
                if relTo.substitutionGroupQname.localName != "domainMemberItem":
                    val.modelXbrl.uuidError("a759f888e0c64c45a5d8f2228cebf33b",
                        modelObject=rel, member=relTo.qname, linkrole=rel.linkrole)
            else:
                if relTo.substitutionGroupQname.localName == "domainMemberItem":
                    val.modelXbrl.uuidError("0e13aed179db48a1acf5becb8f031381",
                        modelObject=rel, domain=relFrom.qname, linkrole=rel.linkrole)
                    break # don't repeat parent's error on rest of child members
                elif relFrom.isAbstract and relFrom.substitutionGroupQname.localName != "primaryDomainItem":
                    val.modelXbrl.uuidError("5b06bd6d6a87428e93a32445cc662b04",
                        modelObject=rel, domain=relFrom.qname, linkrole=rel.linkrole)
                    break # don't repeat parent's error on rest of child members
        '''removed RH 2011-12-06 #check unique set of dimensions per hypercube
        for hc, DRSdims in hypercubeDRSDimensions.items():
            priorELR = None
            priorDRSdims = None
            for ELR, dims in DRSdims.items():
                if priorDRSdims is not None and priorDRSdims != dims:
                    val.modelXbrl.error("SBR.NL.2.3.5.02",
                        _("Hypercube %(hypercube)s has different dimensions in DRS roles %(linkrole)s and %(linkrole2)s: %(dimensions)s and %(dimensions2)s"),
                        modelObject=val.modelXbrl, hypercube=hc.qname, linkrole=ELR, linkrole2=priorELR,
                        dimensions=", ".join([str(dim.qname) for dim in dims]),
                        dimensions2=", ".join([str(dim.qname) for dim in priorDRSdims]))
                priorELR = ELR
                priorDRSdims = dims
        '''
                        
def getDrsRels(val, fromELR, rels, drsELR, drsRelsFrom, drsRelsTo, fromConcepts=None):
    if not fromConcepts: fromConcepts = set()
    for rel in rels:
        relTo = rel.toModelObject
        drsRelsFrom[rel.fromModelObject].append(rel)
        drsRelsTo[relTo].append(rel)
        toELR = rel.targetRole
        if not toELR: toELR = fromELR
        if relTo not in fromConcepts: 
            fromConcepts.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(
                     XbrlConst.domainMember, toELR).fromModelObject(relTo)
            getDrsRels(val, toELR, domMbrRels, drsELR, drsRelsFrom, drsRelsTo, fromConcepts)
            fromConcepts.discard(relTo)
    return False        
    
def undirectedFwdCycle(val, fromELR, rels, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited=None):
    if not ELRsVisited: ELRsVisited = set()
    ELRsVisited.add(fromELR)
    for rel in rels:
        if rel.linkrole == fromELR:
            relTo = rel.toModelObject
            toELR = rel.targetRole
            if not toELR:
                toELR = fromELR
            if relTo in fromConceptELRs and toELR in fromConceptELRs[relTo]: #forms a directed cycle
                return [rel,True]
            fromConceptELRs[relTo].add(toELR)
            if drsRelsFrom:
                domMbrRels = drsRelsFrom[relTo]
            else:
                domMbrRels = val.modelXbrl.relationshipSet(
                         XbrlConst.domainMember, toELR).fromModelObject(relTo)
            cycleCausingConcept = undirectedFwdCycle(val, toELR, domMbrRels, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
            if cycleCausingConcept is not None:
                cycleCausingConcept.append(rel)
                cycleCausingConcept.append(True)
                return cycleCausingConcept
            fromConceptELRs[relTo].discard(toELR)
            # look for back path in any of the ELRs visited (pass None as ELR)
            cycleCausingConcept = undirectedRevCycle(val, None, relTo, rel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
            if cycleCausingConcept is not None:
                cycleCausingConcept.append(rel)
                cycleCausingConcept.append(True)
                return cycleCausingConcept
    return None

def undirectedRevCycle(val, fromELR, mbrConcept, turnbackRel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited):
    for arcrole in (XbrlConst.domainMember, XbrlConst.dimensionDomain):
        '''
        for ELR in ELRsVisited if (not fromELR) else (fromELR,):
            for rel in val.modelXbrl.relationshipSet(arcrole, ELR).toModelObject(mbrConcept):
                if not rel.isIdenticalTo(turnbackRel):
                    relFrom = rel.fromModelObject
                    relELR = rel.linkrole
                    if relFrom in fromConcepts and relELR == drsELR:
                        return True
                    if undirectedRevCycle(val, relELR, relFrom, turnbackRel, drsELR, fromConcepts, ELRsVisited):
                        return True
        '''
        if drsRelsTo:
            mbrDomRels = drsRelsTo[mbrConcept]
        else:
            mbrDomRels = val.modelXbrl.relationshipSet(arcrole, None).toModelObject(mbrConcept)
        for rel in mbrDomRels:
            if not rel.isIdenticalTo(turnbackRel):
                relFrom = rel.fromModelObject
                relELR = rel.linkrole
                if relFrom in fromConceptELRs and relELR in fromConceptELRs[relFrom]:
                    return [rel, False] # turnbackRel.toModelObject
                cycleCausingConcept = undirectedRevCycle(val, relELR, relFrom, turnbackRel, drsELR, drsRelsFrom, drsRelsTo, fromConceptELRs, ELRsVisited)
                if cycleCausingConcept is not None:
                    cycleCausingConcept.append(rel)
                    cycleCausingConcept.append(False)
                    return cycleCausingConcept
    return None

def cyclePath(source, cycles):
    isForward = True
    path = []
    for rel in reversed(cycles):
        if isinstance(rel,bool):
            isForward = rel
        else:
            path.append("{0}:{1} {2}".format(rel.modelDocument.basename, 
                                             rel.sourceline, 
                                             rel.toModelObject.qname if isForward else rel.fromModelObject.qname))
    return str(source.qname) + " " + " - ".join(path)            
                
def commonAncestor(domainMemberRelationshipSet, 
                   negSourceConcept, posSourceConcepts):
    negAncestors = ancestorOrSelf(domainMemberRelationshipSet,negSourceConcept)
    for posSourceConcept in posSourceConcepts:
        if len(negAncestors & ancestorOrSelf(domainMemberRelationshipSet,posSourceConcept)):
            return True
    return False

def ancestorOrSelf(domainMemberRelationshipSet,sourceConcept,result=None):
    if not result:
        result = set()
    if not sourceConcept in result:
        result.add(sourceConcept)
        for rels in domainMemberRelationshipSet.toModelObject(sourceConcept):
            ancestorOrSelf(domainMemberRelationshipSet, rels.fromModelObject, result)
    return result
        
def checkSBRNLMembers(val, hc, dim, domELR, rels, ELR, isDomMbr, members=None, ancestors=None):
    if members is None: members = set()
    if ancestors is None: ancestors = set()
    for rel in rels:
        relFrom = rel.fromModelObject
        relTo = rel.toModelObject
        toELR = rel.targetRole
        if not toELR: 
            toELR = rel.linkrole
        
        if isDomMbr or not relTo.isAbstract:
            if relTo in members:
                val.modelXbrl.relationshipSet(XbrlConst.all).toModelObject(hc)
                if isDomMbr:
                    val.modelXbrl.uuidError("eb26cbddafb5487f9b672c0ba40bb189",
                        modelObject=relTo, dimension=dim.qname, linkrole=ELR, hypercube=hc.qname, concept=relTo.qname) 
                else:
                    val.modelXbrl.uuidError("b19c6ab61c534cce9b1813725b38808f",
                        modelObject=relTo, hypercube=hc.qname, ELR=domELR, concept=relTo.qname, linkrole=ELR)
            members.add(relTo)
        if not isDomMbr: # pri item relationships
            if (relTo.isAbstract and not relFrom.isAbstract or 
                relFrom.substitutionGroupQname.localName != "primaryDomainItem"):
                val.modelXbrl.uuidError("377e5bbdaed147038871e861a157fc7a",
                    modelObject=rel, concept=relTo.qname, linkrole=ELR, hypercube=hc.qname, concept2=relFrom.qname)
        if relTo not in ancestors: 
            ancestors.add(relTo)
            domMbrRels = val.modelXbrl.relationshipSet(
                     XbrlConst.domainMember, toELR).fromModelObject(relTo)
            checkSBRNLMembers(val, hc, dim, domELR, domMbrRels, ELR, isDomMbr, members, ancestors)
            ancestors.discard(relTo)
    return False        
    
