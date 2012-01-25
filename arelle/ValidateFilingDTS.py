'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os, datetime, re
from arelle import (ModelDocument, ModelValue, XmlUtil, XbrlConst, UrlUtil)
from arelle.ModelObject import ModelObject
from arelle.ModelDtsObject import ModelConcept

targetNamespaceDatePattern = None
roleTypePattern = None
arcroleTypePattern = None
arcroleDefinitionPattern = None

def checkDTS(val, modelDocument, visited):
    global targetNamespaceDatePattern, roleTypePattern, arcroleTypePattern, arcroleDefinitionPattern
    if targetNamespaceDatePattern is None:
        targetNamespaceDatePattern = re.compile(r"/([12][0-9]{3})-([01][0-9])-([0-3][0-9])|"
                                            r"/([12][0-9]{3})([01][0-9])([0-3][0-9])|")
        roleTypePattern = re.compile(r".*/role/[^/]+")
        arcroleTypePattern = re.compile(r".*/arcrole/[^/]+")
        arcroleDefinitionPattern = re.compile(r"^.*[^\\s]+.*$")  # at least one non-whitespace character
        
    visited.append(modelDocument)
    definesLabelLinkbase = False
    for referencedDocument in modelDocument.referencesDocument.items():
        #6.07.01 no includes
        if referencedDocument[1] == "include":
            val.modelXbrl.uuidError("28ff84c2bf5b4014bd464beb227f02bb",
                modelObject=modelDocument,
                    schema=os.path.basename(modelDocument.uri), 
                    include=os.path.basename(referencedDocument[0].uri))
        if referencedDocument[0] not in visited:
            checkDTS(val, referencedDocument[0], visited)
            
    if val.disclosureSystem.standardTaxonomiesDict is None:
        pass
    if (modelDocument.type == ModelDocument.Type.SCHEMA and 
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and
        modelDocument.uri.startswith(val.modelXbrl.uriDir)):
        
        # check schema contents types
        if val.validateSBRNL:
            definesLinkroles = False
            definesArcroles = False
            definesLinkParts = False
            definesAbstractItems = False
            definesNonabstractItems = False
            definesConcepts = False
            definesTuples = False
            definesPresentationTuples = False
            definesSpecificationTuples = False
            definesTypes = False
            definesEnumerations = False
            definesDimensions = False
            definesDomains = False
            definesHypercubes = False
            typedDomainElements = set()
                
        # 6.7.3 check namespace for standard authority
        targetNamespaceAuthority = UrlUtil.authority(modelDocument.targetNamespace) 
        if targetNamespaceAuthority in val.disclosureSystem.standardAuthorities:
            val.modelXbrl.uuidError("b02edf4099d44f69be6e9e837e1e8d0c",
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)
            
        # 6.7.4 check namespace format
        if modelDocument.targetNamespace is None:
            match = None
        elif val.validateEFMorGFM:
            targetNamespaceDate = modelDocument.targetNamespace[len(targetNamespaceAuthority):]
            match = targetNamespaceDatePattern.match(targetNamespaceDate)
        else:
            match = None
        if match is not None:
            try:
                if match.lastindex == 3:
                    datetime.date(int(match.group(1)),int(match.group(2)),int(match.group(3)))
                elif match.lastindex == 6:
                    datetime.date(int(match.group(4)),int(match.group(5)),int(match.group(6)))
                else:
                    match = None
            except ValueError:
                match = None
        if match is None:
            val.modelXbrl.uuidError("38fc3b96348e43b9a30f75e4607a68c3",
                modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace)

        if modelDocument.targetNamespace is not None:
            # 6.7.5 check prefix for _
            prefix = XmlUtil.xmlnsprefix(modelDocument.xmlRootElement,modelDocument.targetNamespace)
            if prefix and "_" in prefix:
                val.modelXbrl.uuidError("f488d29d7dbb426b8a7d035b8d62f082",
                    modelObject=modelDocument, schema=os.path.basename(modelDocument.uri), targetNamespace=modelDocument.targetNamespace, prefix=prefix)

            if val.validateSBRNL:
                genrlSpeclRelSet = val.modelXbrl.relationshipSet(XbrlConst.generalSpecial)
            for modelConcept in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.w3.org/2001/XMLSchema}element"):
                if isinstance(modelConcept,ModelConcept):
                    # 6.7.16 name not duplicated in standard taxonomies
                    name = modelConcept.get("name")
                    if name is None: 
                        name = ""
                        if modelConcept.get("ref") is not None:
                            continue    # don't validate ref's here
                    for c in val.modelXbrl.nameConcepts.get(name, []):
                        if c.modelDocument != modelDocument:
                            if (val.validateEFMorGFM and
                                  not c.modelDocument.uri.startswith(val.modelXbrl.uriDir)):
                                val.modelXbrl.uuidError("7a46b3780cf84c7a92a39e82c2db0c2f",
                                    modelObject=c, concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri))
                            elif val.validateSBRNL:
                                if not (genrlSpeclRelSet.isRelated(modelConcept, "child", c) or genrlSpeclRelSet.isRelated(c, "child", modelConcept)):
                                    val.modelXbrl.uuidError("0788abfdaf16400eb2b271293d8fbd9e",
                                        modelObject=c, concept=modelConcept.qname, standardSchema=os.path.basename(c.modelDocument.uri))
                    ''' removed RH 2011-12-23 corresponding set up of table in ValidateFiling
                    if val.validateSBRNL and name in val.nameWordsTable:
                        if not any( any( genrlSpeclRelSet.isRelated(c, "child", modelConcept)
                                         for c in val.modelXbrl.nameConcepts.get(partialWordName, []))
                                    for partialWordName in val.nameWordsTable[name]):
                            val.modelXbrl.error("SBR.NL.2.3.2.01",
                                _("Concept %(specialName)s is appears to be missing a general-special relationship to %(generalNames)s"),
                                modelObject=c, specialName=modelConcept.qname, generalNames=', or to '.join(val.nameWordsTable[name]))
                    '''

                    # 6.7.17 id properly formed
                    id = modelConcept.id
                    requiredId = (prefix if prefix is not None else "") + "_" + name
                    if val.validateEFMorGFM and id != requiredId:
                        val.modelXbrl.uuidError("00fef850cf7947f380835ef5b252a7d0",
                            modelObject=modelConcept, concept=modelConcept.qname, id=id, requiredId=requiredId)
                        
                    # 6.7.18 nillable is true
                    nillable = modelConcept.get("nillable")
                    if nillable != "true":
                        val.modelXbrl.uuidError("d5ed4c1d6cfe485c84f51fe4fe78de36",
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri),
                            concept=name, nillable=nillable)
        
                    # 6.7.19 not tuple
                    if modelConcept.isTuple:
                        if val.validateEFMorGFM:
                            val.modelXbrl.uuidError("f7f0767f11f14058a58efac1e712b6f3",
                                modelObject=modelConcept, concept=modelConcept.qname)
                        
                    # 6.7.20 no typed domain ref
                    if modelConcept.isTypedDimension:
                        val.modelXbrl.uuidError("6d9ef91abfa44084baeba70ef4f60db3",
                            modelObject=modelConcept, concept=modelConcept.qname,
                            typedDomainRef=modelConcept.typedDomainElement.qname if modelConcept.typedDomainElement is not None else modelConcept.typedDomainRef)
                        
                    # 6.7.21 abstract must be duration
                    isDuration = modelConcept.periodType == "duration"
                    if modelConcept.abstract == "true" and not isDuration:
                        val.modelXbrl.uuidError("5863af574dd34c1b87b3c1099659e3a3",
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=name)
                        
                    # 6.7.22 abstract must be stringItemType
                    ''' removed SEC EFM v.17, Edgar release 10.4, and GFM 2011-04-08
                    if modelConcept.abstract == "true" and modelConcept.typeQname != XbrlConst. qnXbrliStringItemType:
                        val.modelXbrl.error(("EFM.6.07.22", "GFM.1.03.24"),
                            _("Concept %(concept)s  is abstract but type is not xbrli:stringItemType"),
                            modelObject=modelConcept, concept=modelConcept.qname)
					'''
                    substititutionGroupQname = modelConcept.substitutionGroupQname
                    # 6.7.23 Axis must be subs group dimension
                    if name.endswith("Axis") ^ (substititutionGroupQname == XbrlConst.qnXbrldtDimensionItem):
                        val.modelXbrl.uuidError("55321dbf2feb481fa8fec20763efe43b",
                            modelObject=modelConcept, concept=modelConcept.qname)

                    # 6.7.24 Table must be subs group hypercube
                    if name.endswith("Table") ^ (substititutionGroupQname == XbrlConst.qnXbrldtHypercubeItem):
                        val.modelXbrl.uuidError("0e3ef0eda03d4644b620acd6993fdedf",
                            modelObject=modelConcept, schema=os.path.basename(modelDocument.uri), concept=modelConcept.qname)

                    # 6.7.25 if neither hypercube or dimension, substitution group must be item
                    if substititutionGroupQname not in (None,
                                                        XbrlConst.qnXbrldtDimensionItem, 
                                                        XbrlConst.qnXbrldtHypercubeItem,
                                                        XbrlConst.qnXbrliItem):                           
                        val.modelXbrl.uuidError("bda86e4842de497c9d49728985bacfd9",
                            modelObject=modelConcept, concept=modelConcept.qname,
                            substitutionGroup=modelConcept.substitutionGroupQname)
                        
                    # 6.7.26 Table must be subs group hypercube
                    if name.endswith("LineItems") and modelConcept.abstract != "true":
                        val.modelXbrl.uuidError("fb5470b8b8f74e249a2eef5b478ce88a",
                            modelObject=modelConcept, concept=modelConcept.qname)

                    # 6.7.27 type domainMember must end with Domain or Member
                    conceptType = modelConcept.type
                    isDomainItemType = conceptType is not None and conceptType.isDomainItemType
                    endsWithDomainOrMember = name.endswith("Domain") or name.endswith("Member")
                    if isDomainItemType != endsWithDomainOrMember:
                        val.modelXbrl.uuidError("75fc8248320742ecb53b8583b6e3eb10",
                            modelObject=modelConcept, concept=modelConcept.qname)

                    # 6.7.28 domainItemType must be duration
                    if isDomainItemType and not isDuration:
                        val.modelXbrl.uuidError("c2b598c783624009ad28cb67b75e7431",
                            modelObject=modelConcept, concept=modelConcept.qname)
                    
                    if val.validateSBRNL:
                        if modelConcept.isTuple:
                            if modelConcept.substitutionGroupQname.localName == "presentationTuple" and modelConcept.substitutionGroupQname.namespaceURI.endswith("/basis/sbr/xbrl/xbrl-syntax-extension"): # namespace may change each year
                                definesPresentationTuples = True
                            elif modelConcept.substitutionGroupQname.localName == "specificationTuple" and modelConcept.substitutionGroupQname.namespaceURI.endswith("/basis/sbr/xbrl/xbrl-syntax-extension"): # namespace may change each year
                                definesSpecificationTuples = True
                            else:
                                definesTuples = True
                            definesConcepts = True
                            if modelConcept.abstract == "true":
                                val.modelXbrl.uuidError("1a78fa3feed440c3b3ed27219d72e9cf",
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if tupleCycle(val,modelConcept):
                                val.modelXbrl.uuidError("b308ccd62ac44f2eb12426a0cc20dfcf",
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.get("nillable") != "false" and modelConcept.isRoot:
                                val.modelXbrl.uuidError("4864e78cb04a41698443d012fd50481b", #don't want default, just what was really there
                                    modelObject=modelConcept, concept=modelConcept.qname)
                        elif modelConcept.isItem:
                            definesConcepts = True
                        if modelConcept.abstract == "true":
                            if modelConcept.isRoot:
                                if modelConcept.get("nillable") != "false": #don't want default, just what was really there
                                    val.modelXbrl.uuidError("340fd16490634cdb926aad192f3ec63a",
                                    modelObject=modelConcept, concept=modelConcept.qname)
                                if modelConcept.typeQname != XbrlConst.qnXbrliStringItemType:
                                    val.modelXbrl.uuidError("8aac264848e545888d6057b265f5c9b5",
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.balance:
                                val.modelXbrl.uuidError("784b1b7cd14a4b7da91ddb6974d018e4",
                                    modelObject=modelConcept, concept=modelConcept.qname)
                            if modelConcept.isHypercubeItem:
                                definesHypercubes = True
                            elif modelConcept.isDimensionItem:
                                definesDimensions = True
                            elif substititutionGroupQname and substititutionGroupQname.localName in ("domainItem","domainMemberItem"):
                                definesDomains = True
                            elif modelConcept.isItem:
                                definesAbstractItems = True
                        else:   # not abstract
                            if modelConcept.isItem:
                                definesNonabstractItems = True
                                if not (modelConcept.label(preferredLabel=XbrlConst.documentationLabel,fallbackToQname=False,lang="nl") or
                                        val.modelXbrl.relationshipSet(XbrlConst.conceptReference).fromModelObject(c) or
                                        modelConcept.genLabel(role=XbrlConst.genDocumentationLabel,lang="nl") or
                                        val.modelXbrl.relationshipSet(XbrlConst.elementReference).fromModelObject(c)):
                                    val.modelXbrl.uuidError("2183824c1770496bbfdf59a893d2741a",
                                        modelObject=modelConcept, concept=modelConcept.qname)
                        if modelConcept.balance and not modelConcept.instanceOfType(XbrlConst.qnXbrliMonetaryItemType):
                            val.modelXbrl.uuidError("a0750e104d82415bb16505721a642d18",
                                modelObject=modelConcept, concept=modelConcept.qname)
                        if modelConcept.isLinkPart:
                            definesLinkParts = True
                            val.modelXbrl.uuidError("09c383de7ec444259ed3a5864bc3619e",
                                modelObject=modelConcept, concept=modelConcept.qname)
                            if not modelConcept.genLabel(fallbackToQname=False,lang="nl"):
                                val.modelXbrl.uuidError("0ab0cacc39284aa985c7b7b9597c9075",
                                    modelObject=modelConcept, concept=modelConcept.qname)
                        if modelConcept.isTypedDimension:
                            domainElt = modelConcept.typedDomainElement
                            if domainElt is not None:
                                typedDomainElements.add(domainElt)
        # 6.7.8 check for embedded linkbase
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}linkbase"):
            if isinstance(e,ModelObject):
                val.modelXbrl.uuidError("6de7f77e8e3144f7a16c2089a2e9ac2e",
                    modelObject=e, schema=os.path.basename(modelDocument.uri))
                break

        requiredUsedOns = {XbrlConst.qnLinkPresentationLink,
                           XbrlConst.qnLinkCalculationLink,
                           XbrlConst.qnLinkDefinitionLink}

        # 6.7.9 role types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}roleType"):
            if isinstance(e,ModelObject):
                roleURI = e.get("roleURI")
                if targetNamespaceAuthority != UrlUtil.authority(roleURI):
                    val.modelXbrl.uuidError("b3dddf0990964feb99d4f4a6e30efd63",
                        modelObject=e, roleType=roleURI, targetNamespaceAuthority=targetNamespaceAuthority)
                # 6.7.9 end with .../role/lc3 name
                if not roleTypePattern.match(roleURI):
                    val.modelXbrl.uuidWarning("c6cd98f4bd3c412ea36c919d3f1920be",
                        modelObject=e, roleType=roleURI)
                    
                # 6.7.10 only one role type declaration in DTS
                modelRoleTypes = val.modelXbrl.roleTypes.get(roleURI)
                if modelRoleTypes is not None:
                    modelRoleType = modelRoleTypes[0]
                    definition = modelRoleType.definitionNotStripped
                    usedOns = modelRoleType.usedOns
                    if len(modelRoleTypes) > 1:
                        val.modelXbrl.uuidError("a2bcafe90e984d648086beb374351f1f",
                            modelObject=e, roleType=roleURI)
                    elif len(modelRoleTypes) == 1:
                        # 6.7.11 used on's for pre, cal, def if any has a used on
                        if not usedOns.isdisjoint(requiredUsedOns) and len(requiredUsedOns - usedOns) > 0:
                            val.modelXbrl.uuidError("a02927ffad4e46c09de7d39d901cdcab",
                                modelObject=e, roleType=roleURI, usedOn=requiredUsedOns - usedOns)
                            
                        # 6.7.12 definition match pattern
                        if (val.disclosureSystem.roleDefinitionPattern is not None and
                            (definition is None or not val.disclosureSystem.roleDefinitionPattern.match(definition))):
                            val.modelXbrl.uuidError("860ae0a3ac7e4335b7559483b08c41f1",
                                modelObject=e, roleType=roleURI, definition=definition)
                        
                    if val.validateSBRNL:
                        if usedOns & XbrlConst.standardExtLinkQnames or XbrlConst.qnGenLink in usedOns:
                            definesLinkroles = True
                            if not e.genLabel():
                                val.modelXbrl.uuidError("9a14a2e8dc844ea8a775da1ebb87fc83",
                                    modelObject=e, roleType=roleURI)
                            nlLabel = e.genLabel(lang="nl")
                            if definition != nlLabel:
                                val.modelXbrl.uuidError("4ac68d04fbc04d9ea1e415cccf702349",
                                    modelObject=e, roleType=roleURI, definition=definition, label=nlLabel)
                        if definition and (definition[0].isspace() or definition[-1].isspace()):
                            val.modelXbrl.uuidError("d581f0baeb4d4aa2abe3ed1195bd4e69",
                                modelObject=e, roleType=roleURI, definition=definition)

        # 6.7.13 arcrole types authority
        for e in modelDocument.xmlRootElement.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}arcroleType"):
            if isinstance(e,ModelObject):
                arcroleURI = e.get("arcroleURI")
                if targetNamespaceAuthority != UrlUtil.authority(arcroleURI):
                    val.modelXbrl.uuidError("b7e95e5c3efa47fe993dafade47f3877",
                        modelObject=e, arcroleType=arcroleURI, targetNamespaceAuthority=targetNamespaceAuthority)
                # 6.7.13 end with .../arcrole/lc3 name
                if not arcroleTypePattern.match(arcroleURI):
                    val.modelXbrl.uuidWarning("e24497b6a089482b85363588b3336938",
                        modelObject=e, arcroleType=arcroleURI)

                # 6.7.14 only one arcrole type declaration in DTS
                modelRoleTypes = val.modelXbrl.arcroleTypes[arcroleURI]
                if len(modelRoleTypes) > 1:
                    val.modelXbrl.uuidError("d83bfca825b44b6d8c951b7a759186f2",
                        modelObject=e, arcroleType=arcroleURI)
                    
                # 6.7.15 definition match pattern
                definition = modelRoleTypes[0].definition
                if definition is None or not arcroleDefinitionPattern.match(definition):
                    val.modelXbrl.uuidError("1ad7ccc99e9c46b7b4df8413828060eb",
                        modelObject=e, arcroleType=arcroleURI)
    
                if val.validateSBRNL:
                    definesArcroles = True
                    val.modelXbrl.uuidError("501fd785d66f4bd19ff75a2bc45896fa",
                        modelObject=e, arcroleURI=arcroleURI)
                    
        if val.validateSBRNL:
            for domainElt in typedDomainElements:
                if not domainElt.genLabel(fallbackToQname=False,lang="nl"):
                    val.modelXbrl.uuidError("c63e183a435e492894f0481b428acab9",
                        modelObject=domainElt, concept=domainElt.qname)
                if domainElt.type is not None and domainElt.type.find("{http://www.w3.org/2001/XMLSchema}complexType") is not None:
                    val.modelXbrl.uuidError("0f9472ff7bfd43b99a941a97fd42f587",
                        modelObject=domainElt, concept=domainElt.qname)
                    
            for appinfoElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}appinfo"):
                for nonLinkElt in appinfoElt.iterdescendants():
                    if isinstance(nonLinkElt, ModelObject) and nonLinkElt.namespaceURI != XbrlConst.link:
                        val.modelXbrl.uuidError("b450ad822ee843b285f94019a6698bee",
                            modelObject=nonLinkElt, element=nonLinkElt.qname)

            for cplxTypeElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}complexType"):
                choiceElt = cplxTypeElt.find("{http://www.w3.org/2001/XMLSchema}choice")
                if choiceElt is not None:
                    val.modelXbrl.uuidError("3acfa126d6c545efb886a14409f63306",
                        modelObject=choiceElt)
                    
            for cplxContentElt in modelDocument.xmlRootElement.iter(tag="{http://www.w3.org/2001/XMLSchema}complexContent"):
                if XmlUtil.descendantAttr(cplxContentElt, "http://www.w3.org/2001/XMLSchema", "extension", "base") != "sbr:placeholder":
                    val.modelXbrl.uuidError("68fcffd6cc2145379be4bdd158fdb578",
                        modelObject=cplxContentElt)

            definesTypes = (modelDocument.xmlRootElement.find("{http://www.w3.org/2001/XMLSchema}complexType") is not None or
                            modelDocument.xmlRootElement.find("{http://www.w3.org/2001/XMLSchema}simpleType") is not None)
            if (definesLinkroles + definesArcroles + definesLinkParts +
                definesAbstractItems + definesNonabstractItems + 
                definesTuples + definesPresentationTuples + definesSpecificationTuples + definesTypes +
                definesEnumerations + definesDimensions + definesDomains + 
                definesHypercubes) != 1:
                schemaContents = []
                if definesLinkroles: schemaContents.append(_("linkroles"))
                if definesArcroles: schemaContents.append(_("arcroles"))
                if definesLinkParts: schemaContents.append(_("link parts"))
                if definesAbstractItems: schemaContents.append(_("abstract items"))
                if definesNonabstractItems: schemaContents.append(_("nonabstract items"))
                if definesTuples: schemaContents.append(_("tuples"))
                if definesPresentationTuples: schemaContents.append(_("sbrPresentationTuples"))
                if definesSpecificationTuples: schemaContents.append(_("sbrSpecificationTuples"))
                if definesTypes: schemaContents.append(_("types"))
                if definesEnumerations: schemaContents.append(_("enumerations"))
                if definesDimensions: schemaContents.append(_("dimensions"))
                if definesDomains: schemaContents.append(_("domains"))
                if definesHypercubes: schemaContents.append(_("hypercubes"))
                if schemaContents:
                    val.modelXbrl.uuidError("56659065ec794d36a39ddbbb9f2f192c",
                        modelObject=modelDocument, contents=', '.join(schemaContents))
                elif not any(refDoc.inDTS and refDoc.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces
                             for refDoc in modelDocument.referencesDocument.keys()): # no linkbase ref or includes
                    val.modelXbrl.uuidError("3df5f092bdf64fe78e8ba2b87f814d67",
                        modelObject=modelDocument)
            if definesConcepts ^ any(  # xor so either concepts and no label LB or no concepts and has label LB
                       (refDoc.type == ModelDocument.Type.LINKBASE and
                        XmlUtil.descendant(refDoc.xmlRootElement, XbrlConst.link, "labelLink") is not None)
                       for refDoc in modelDocument.referencesDocument.keys()): # no label linkbase
                val.modelXbrl.uuidError("54617d1d8794453795f951337d397ca7",
                    modelObject=modelDocument)
            if (definesNonabstractItems or definesTuples) ^ any(  # xor so either concepts and no ref LB or no concepts and has ref LB
                       (refDoc.type == ModelDocument.Type.LINKBASE and
                       (XmlUtil.descendant(refDoc.xmlRootElement, XbrlConst.link, "referenceLink") is not None or
                        XmlUtil.descendant(refDoc.xmlRootElement, XbrlConst.link, "label", "{http://www.w3.org/1999/xlink}role", "http://www.xbrl.org/2003/role/documentation" ) is not None))
                        for refDoc in modelDocument.referencesDocument.keys()):
                val.modelXbrl.uuidError("b9b32b8aea6a4b47932403afc0be8eee",
                    modelObject=modelDocument)

    visited.remove(modelDocument)
    
def tupleCycle(val, concept, ancestorTuples=None):
    if ancestorTuples is None: ancestorTuples = set()
    if concept in ancestorTuples:
        return True
    ancestorTuples.add(concept)
    if concept.type is not None:
        for elementQname in concept.type.elements:
            childConcept = val.modelXbrl.qnameConcepts.get(elementQname)
            if childConcept is not None and tupleCycle(val, childConcept, ancestorTuples):
                return True
    ancestorTuples.discard(concept)
    return False
