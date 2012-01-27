'''
Created on Nov 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import ModelVersObject, XbrlConst, ValidateXbrl, ModelDocument

conceptAttributeEventAttributes = {
        "conceptAttributeDelete": ("fromCustomAttribute",),
        "conceptAttributeAdd": ("toCustomAttribute",),
        "conceptAttributeChange": ("fromCustomAttribute","toCustomAttribute"),
        }

class ValidateVersReport():
    def __init__(self, testModelXbrl):
        self.testModelXbrl = testModelXbrl  # testcase or controlling validation object

    def close(self):
        self.__dict__.clear()   # dereference everything
        
    def validate(self, modelVersReport):
        self.modelVersReport = modelVersReport
        versReport = modelVersReport.modelDocument
        if not hasattr(versReport, "xmlDocument"): # not parsed
            return
        for DTSname in ("fromDTS", "toDTS"):
            DTSmodelXbrl = getattr(versReport, DTSname)
            if DTSmodelXbrl is None or DTSmodelXbrl.modelDocument is None:
                self.modelVersReport.uuidError("49199ff4f333420fbfdc6474b7911bb6",
                    modelObject=self, dts=DTSname)
            else:
                # validate DTS
                ValidateXbrl.ValidateXbrl(DTSmodelXbrl).validate(DTSmodelXbrl)
                if len(DTSmodelXbrl.errors) > 0:
                    self.modelVersReport.uuidError("96cea9f3a6a9495fbf674ac1441c3dcc",
                        modelObject=DTSmodelXbrl.modelDocument, dts=DTSname, error=DTSmodelXbrl.errors)
        # validate linkbases
        ValidateXbrl.ValidateXbrl(self.modelVersReport).validate(modelVersReport)

        versReportElt = versReport.xmlRootElement
        # check actions
        for assignmentRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}assignmentRef"):
            ref = assignmentRef.get("ref")
            if ref not in versReport.idObjects or \
               not isinstance(versReport.idObjects[ref], ModelVersObject.ModelAssignment):
                    self.modelVersReport.uuidError("99cd2d743b5348c4b2e0339a9a4b251b",
                        modelObject=assignmentRef, assignmentRef=ref)
                    
        # check namespace renames
        for NSrename in versReport.namespaceRenameFrom.values():
            if NSrename.fromURI not in versReport.fromDTS.namespaceDocs:
                self.modelVersReport.uuidError("be82407bfb0c4915ac2cbd4a9a7e0fa3",
                    modelObject=self, uri=NSrename.fromURI)
            if NSrename.toURI not in versReport.toDTS.namespaceDocs:
                self.modelVersReport.uuidError("80b8e3babd7748ed99012379dd7bbc70",
                    modelObject=self, uri=NSrename.toURI)
                
        # check role changes
        for roleChange in versReport.roleChanges.values():
            if roleChange.fromURI not in versReport.fromDTS.roleTypes:
                self.modelVersReport.uuidError("3748c77a7fcc4fe7aad0f706451668c1",
                    modelObject=self, uri=roleChange.fromURI)
            if roleChange.toURI not in versReport.toDTS.roleTypes:
                self.modelVersReport.uuidError("0f754f386a424b638b666a33b257ab17",
                    modelObject=self, uri=roleChange.toURI)
                
        # check reportRefs
        # check actions
        for reportRef in versReportElt.iterdescendants(tag="{http://xbrl.org/2010/versioning-base}reportRef"):
            xlinkType = reportRef.get("{http://www.w3.org/1999/xlink}type")
            if xlinkType != "simple":
                self.modelVersReport.uuidError("fb5a6b06e4a0466ebe37b96b9fbc69b6",
                    modelObject=reportRef, xlinkType=xlinkType)
            # if existing it must be valid
            href = reportRef.get("{http://www.w3.org/1999/xlink}href")
            # TBD
            
            arcrole = reportRef.get("{http://www.w3.org/1999/xlink}arcrole")
            if arcrole is None:
                self.modelVersReport.uuidError("69d8dd11586b4f2f85b66bda037ee7e6",
                    modelObject=reportRef)
            else:
                if arcrole != "http://xbrl.org/arcrole/2010/versioning/related-report":
                    self.modelVersReport.uuidError("2689eb03c3b64c7d8540b57ad206f58b",
                        modelObject=reportRef, arcrole=arcrole)
            
        if versReport.fromDTS and versReport.toDTS:
            # check concept changes of concept basic
            for conceptChange in versReport.conceptBasicChanges:
                if conceptChange.name != "conceptAdd" and \
                   (conceptChange.fromConcept is None or \
                    conceptChange.fromConcept.qname not in versReport.fromDTS.qnameConcepts):
                    self.modelVersReport.uuidError("21f0ef390edc42deac2b067ba2b15444",
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.fromConceptQname) 
                if conceptChange.name != "conceptDelete" and \
                   (conceptChange.toConcept is None or \
                    conceptChange.toConcept.qname not in versReport.toDTS.qnameConcepts):
                    self.modelVersReport.uuidError("d46b06983fdc46f2a8b00241d5366dfd",
                        modelObject=conceptChange, event=conceptChange.name, concept=conceptChange.toConceptQname) 
                    
            # check concept changes of concept extended
            for conceptChange in versReport.conceptExtendedChanges:
                fromConcept = conceptChange.fromConcept
                toConcept = conceptChange.toConcept
                fromResource = conceptChange.fromResource
                toResource = conceptChange.toResource
                # fromConcept checks
                if not conceptChange.name.endswith("Add"):
                    if not fromConcept is not None:
                        self.modelVersReport.uuidError("b286263b3cdc49ebaaebf79c72eba257",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.fromConceptQname) 
                    # tuple check
                    elif _("Child") in conceptChange.name and \
                        not versReport.fromDTS.qnameConcepts[fromConcept.qname] \
                            .isTuple:
                        self.modelVersReport.uuidError("697ede10ab6b43b7908b7a51250084b9",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.fromConceptQname) 
                    # resource check
                    elif "Label" in conceptChange.name:
                        if fromResource is None:
                            self.modelVersReport.uuidError("f7a4442d7a2e4003b95239ae14d54640",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.fromResourceValue) 
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptLabel)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   fromResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.uuidError("4d0957e6e26841e0bc64c6affb12d5ec",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementLabel)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.uuidError("4d0957e6e26841e0bc64c6affb12d5ec",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                                else:
                                    self.modelVersReport.uuidError("2e3e8a455b4e429796ed62cd45c2ddb2",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue)
                    elif "Reference" in conceptChange.name:
                        if fromResource is None:
                            self.modelVersReport.uuidError("1e3889b6b6684f3194b516f78cda5f36",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.fromResourceValue)
                        else:
                            relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.conceptReference)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   fromResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.uuidError("519eae9c67db478eaa82eb41ca5325ff",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                            else:
                                relationship = fromConcept.relationshipToResource(fromResource, XbrlConst.elementReference)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       fromResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.uuidError("519eae9c67db478eaa82eb41ca5325ff",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                                else:
                                    self.modelVersReport.uuidError("1b7ba287762a4ad3973d062cadc19e73",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.fromResourceValue, concept=conceptChange.fromConceptQname)
                             
                # toConcept checks
                if not conceptChange.name.endswith("Delete"):
                    if not toConcept is not None:
                        self.modelVersReport.uuidError("695368668d4945ddaffb0327ff26f9e1",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.toConceptQname)
                    # tuple check
                    elif "Child" in conceptChange.name and \
                        not versReport.toDTS.qnameConcepts[toConcept.qname] \
                            .isTuple:
                        self.modelVersReport.uuidError("a31823e41691408faf7efd02b43f3608",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, concept=conceptChange.toConceptQname)
                    # resource check
                    elif "Label" in conceptChange.name:
                        if toResource is None:
                            self.modelVersReport.uuidError("de72f687097c4d1a91c0145202af1855",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptLabel)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkLabelArc or \
                                   relationship.parentQname != XbrlConst.qnLinkLabelLink or \
                                   toResource.qname != XbrlConst.qnLinkLabel:
                                    self.modelVersReport.uuidError("34af4b23e61848d988d5e1428aefeba7",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementLabel)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenLabel:
                                        self.modelVersReport.uuidError("34af4b23e61848d988d5e1428aefeba7",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                                else:
                                    self.modelVersReport.uuidError("a8df9963bd434b9594b825bdd3d9b1cb",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                    elif "Reference" in conceptChange.name:
                        if toResource is None:
                            self.modelVersReport.uuidError("4e63ed7357ed4f5798a551ab222583d9",
                                modelObject=conceptChange, action=conceptChange.actionId,
                                event=conceptChange.name, resource=conceptChange.toResourceValue)
                        else:
                            relationship = toConcept.relationshipToResource(toResource, XbrlConst.conceptReference)
                            if relationship is not None:
                                if relationship.qname != XbrlConst.qnLinkReferenceArc or \
                                   relationship.parentQname != XbrlConst.qnLinkReferenceLink or \
                                   toResource.qname != XbrlConst.qnLinkReference:
                                    self.modelVersReport.uuidError("b35c3c23fcc4412c9a9af37b45dc3157",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                            else:
                                relationship = toConcept.relationshipToResource(toResource, XbrlConst.elementReference)
                                if relationship is not None:
                                    if relationship.qname != XbrlConst.qnGenArc or \
                                       toResource.qname != XbrlConst.qnGenReference:
                                        self.modelVersReport.uuidError("b35c3c23fcc4412c9a9af37b45dc3157",
                                            modelObject=conceptChange, action=conceptChange.actionId,
                                            event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                                else:
                                    self.modelVersReport.uuidError("35bc7bb82e2a40ab9e70bcb18d757dc6",
                                        modelObject=conceptChange, action=conceptChange.actionId,
                                        event=conceptChange.name, resource=conceptChange.toResourceValue, concept=conceptChange.toConceptQname)
                        
                # check concept correspondence
                if fromConcept is not None and toConcept is not None:
                    if versReport.toDTSqname(fromConcept.qname) != toConcept.qname and \
                       versReport.equivalentConcepts.get(fromConcept.qname) != toConcept.qname and \
                       toConcept.qname not in versReport.relatedConcepts.get(fromConcept.qname,[]):
                        self.modelVersReport.uuidError("abfc667d38d649f3aaba642323bf8061",
                            modelObject=conceptChange, action=conceptChange.actionId,
                            event=conceptChange.name, conceptFrom=conceptChange.fromConceptQname, conceptTo=conceptChange.toConceptQname)
    
                # custom attribute events
                if conceptChange.name.startswith("conceptAttribute"):
                    try:
                        for attr in conceptAttributeEventAttributes[conceptChange.name]:
                            customAttributeQname = conceptChange.customAttributeQname(attr)
                            if not customAttributeQname or customAttributeQname.namespaceURI is None:
                                self.modelVersReport.uuidError("abfc667d38d649f3aaba642323bf8061",
                                    modelObject=conceptChange, action=conceptChange.actionId,
                                    attr=attr, attrName=customAttributeQname)
                            elif customAttributeQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.xsd):
                                self.modelVersReport.uuidError("413c0fada71b47ae845168dd883892f8",
                                    modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name,
                                    attr=attr, attrName=customAttributeQname)
                    except KeyError:
                        self.modelVersReport.uuidInfo("0781e4b5e2d94e99b027bf40cd8c5d18",
                            modelObject=conceptChange, action=conceptChange.actionId, event=conceptChange.name)
    
            # check relationship set changes
            for relSetChange in versReport.relationshipSetChanges:
                for relationshipSet, name in ((relSetChange.fromRelationshipSet, "fromRelationshipSet"),
                                              (relSetChange.toRelationshipSet, "toRelationshipSet")):
                    if relationshipSet is not None:
                        relationshipSetValid = True
                        if relationshipSet.link and relationshipSet.link not in relationshipSet.dts.qnameConcepts:
                            self.modelVersReport.uuidError("09f1239452c14bfa8f621ccb3a8eda0d",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                link=relationshipSet.link)
                            relationshipSetValid = False
                        if relationshipSet.arc and relationshipSet.arc not in relationshipSet.dts.qnameConcepts:
                            self.modelVersReport.uuidError("aabad0af3cf344729a3caff56f6fd169",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                arc=relationshipSet.arc)
                            relationshipSetValid = False
                        if relationshipSet.linkrole and not (XbrlConst.isStandardRole(relationshipSet.linkrole) or
                                                             relationshipSet.linkrole in relationshipSet.dts.roleTypes):
                            self.modelVersReport.uuidError("c20767aebda94d0b9e323d43739dbba8",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                linkrole=relationshipSet.linkrole)
                            relationshipSetValid = False
                        if relationshipSet.arcrole and not (XbrlConst.isStandardArcrole(relationshipSet.arcrole) or
                                                            relationshipSet.arcrole in relationshipSet.dts.arcroleTypes):
                            self.modelVersReport.uuidError("c12714052b0a48faa6a9065cb1637aa8",
                                modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                arcrole=relationshipSet.arcrole)
                            relationshipSetValid = False
                        for relationship in relationshipSet.relationships:
                            # fromConcept checks
                            if relationship.fromConcept is None:
                                self.modelVersReport.uuidError("eb519a0bbb0143189d191b30e542970b",
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptFrom=relationship.fromName)
                                relationshipSetValid = False
                            if relationship.toName and relationship.toConcept is None:
                                self.modelVersReport.uuidError("75839520db154486b6a732f280896b39",
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptTo=relationship.toName)
                                relationshipSetValid = False
                            if relationshipSetValid: # test that relations exist
                                if relationship.fromRelationship is None:
                                    if relationship.toName:
                                        self.modelVersReport.uuidError("100d51782f6040808de31f43f7eab21b",
                                    modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                    conceptFrom=relationship.fromName, conceptTo=relationship.toName)
                                    else:
                                        self.modelVersReport.uuidError("2ea990d8a1714bae9d93876840b09b84",
                                            modelObject=relSetChange, event=relSetChange.name, relSet=name,
                                            conceptFrom=relationship.fromName)
                                    

                        
            
            '''
            # check instance aspect changes
            for iaChange in versReport.instanceAspectChanges:
                # validate related concepts
                for aspectName in ("{http://xbrl.org/2010/versioning-instance-aspects}concept", "{http://xbrl.org/2010/versioning-instance-aspects}member"):
                    for aspectElt in iaChange.iterdescendants(aspectName):
                        # check link attribute
                        link = aspectElement.get("link")
                        if link is not None:
                            iaChange.hrefToModelObject(link, dts)
            '''
            
        self.close()