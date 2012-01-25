'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom, xml.parsers
import os, re, collections, datetime
from collections import defaultdict
from arelle import (ModelDocument, ModelValue, ValidateXbrl,
                ModelRelationshipSet, XmlUtil, XbrlConst, UrlUtil,
                ValidateFilingDimensions, ValidateFilingDTS, ValidateFilingText)
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelDtsObject import ModelConcept

datePattern = None

class ValidateFiling(ValidateXbrl.ValidateXbrl):
    def __init__(self, modelXbrl):
        super().__init__(modelXbrl)
        
        global datePattern, GFMcontextDatePattern, signOrCurrencyPattern, usTypesPattern, usRolesPattern, usDeiPattern
        
        if datePattern is None:
            datePattern = re.compile(r"([12][0-9]{3})-([01][0-9])-([0-3][0-9])")
            GFMcontextDatePattern = re.compile(r"^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$")
            signOrCurrencyPattern = re.compile("^(-)[0-9]+|[^eE](-)[0-9]+|(\\()[0-9].*(\\))|([$\u20ac£¥])")
            usTypesPattern = re.compile(r"^http://(xbrl.us|fasb.org)/us-types/")
            usRolesPattern = re.compile(r"^http://(xbrl.us|fasb.org)/us-roles/")
            usDeiPattern = re.compile(r"http://(xbrl.us|xbrl.sec.gov)/dei/")

        
    def validate(self, modelXbrl, parameters=None):
        if not hasattr(modelXbrl.modelDocument, "xmlDocument"): # not parsed
            return
        
        modelXbrl.modelManager.disclosureSystem.loadStandardTaxonomiesDict()
        
        # find typedDomainRefs before validateXBRL pass
        if modelXbrl.modelManager.disclosureSystem.SBRNL:
            self.qnSbrLinkroleorder = ModelValue.qname("http://www.nltaxonomie.nl/5.0/basis/sbr/xbrl/xbrl-syntax-extension","linkroleOrder")

            self.typedDomainQnames = set()
            for modelConcept in modelXbrl.qnameConcepts.values():
                if modelConcept.isTypedDimension:
                    typedDomainElement = modelConcept.typedDomainElement
                    if typedDomainElement is not None:
                        self.typedDomainQnames.add(typedDomainElement.qname)
        
        # note that some XFM tests are done by ValidateXbrl to prevent mulstiple node walks
        super(ValidateFiling,self).validate(modelXbrl, parameters)
        xbrlInstDoc = modelXbrl.modelDocument.xmlDocument.getroot()
        disclosureSystem = self.disclosureSystem
        _isStandardUri = {}
        
        def isStandardUri(uri):
            try:
                return _isStandardUri[uri]
            except KeyError:
                isStd = (uri in disclosureSystem.standardTaxonomiesDict or
                         (not uri.startswith("http://") and 
                          # try 2011-12-23 RH: if works, remove the localHrefs
                          # any(u.endswith(e) for u in (uri.replace("\\","/"),) for e in disclosureSystem.standardLocalHrefs)
                          "/basis/sbr/" in uri.replace("\\","/")
                          ))
                _isStandardUri[uri] = isStd
                return isStd

        modelXbrl.modelManager.showStatus(_("validating {0}").format(disclosureSystem.name))
        
        self.modelXbrl.profileActivity()
        conceptsUsed = {} # key=concept object value=True if has presentation label
        labelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.conceptLabel)
        if self.validateSBRNL:  # include generic labels in a (new) set
            genLabelsRelationshipSet = modelXbrl.relationshipSet(XbrlConst.elementLabel)
        presentationRelationshipSet = modelXbrl.relationshipSet(XbrlConst.parentChild)
        referencesRelationshipSetWithProhibits = modelXbrl.relationshipSet(XbrlConst.conceptReference, includeProhibits=True)
        self.modelXbrl.profileActivity("... cache lbl, pre, ref relationships", minTimeToShow=1.0)
        
        validateInlineXbrlGFM = (modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL and
                                 self.validateGFM)
        
        # instance checks
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            #6.5.1 scheme, 6.5.2, 6.5.3 identifier
            entityIdentifierValue = None
            if disclosureSystem.identifierValueName:   # omit if no checks
                for entityIdentifierElt in xbrlInstDoc.iterdescendants("{http://www.xbrl.org/2003/instance}identifier"):
                    if isinstance(entityIdentifierElt,ModelObject):
                        schemeAttr = entityIdentifierElt.get("scheme")
                        if not disclosureSystem.identifierSchemePattern.match(schemeAttr):
                            modelXbrl.uuidError("94c39d475f1f41d28b894614677ca9f4",
                                modelObject=entityIdentifierElt, scheme=schemeAttr)
                        entityIdentifier = XmlUtil.text(entityIdentifierElt)
                        if not disclosureSystem.identifierValuePattern.match(entityIdentifier):
                            modelXbrl.uuidError("030ba9669b2c4d5a8ca34ab976703fa7",
                                modelObject=entityIdentifierElt,  
                                entityIdentifierName=disclosureSystem.identifierValueName,
                                entityIdentifer=entityIdentifier)
                        if not entityIdentifierValue:
                            entityIdentifierValue = entityIdentifier
                        elif entityIdentifier != entityIdentifierValue:
                            modelXbrl.uuidError("e79bb91c7dec4373964a30daa373021d",
                                modelObject=entityIdentifierElt,  
                                entityIdentifierName=disclosureSystem.identifierValueName,
                                entityIdentifer=entityIdentifierValue,
                                entityIdentifer2=entityIdentifier) 
                self.modelXbrl.profileActivity("... filer identifier checks", minTimeToShow=1.0)
    
            #6.5.7 duplicated contexts
            contexts = modelXbrl.contexts.values()
            contextIDs = set()
            uniqueContextHashes = {}
            for context in contexts:
                contextID = context.id
                contextIDs.add(contextID)
                h = context.contextDimAwareHash
                if h in uniqueContextHashes:
                    if context.isEqualTo(uniqueContextHashes[h]):
                        modelXbrl.uuidError("bb57b0bcb99f4ef99a352c042372c745",
                            modelObject=context, context=contextID, context2=uniqueContextHashes[h].id)
                else:
                    uniqueContextHashes[h] = context
                    
                #GFM no time in contexts
                if self.validateGFM:
                    for dateElt in XmlUtil.children(context, XbrlConst.xbrli, ("startDate", "endDate", "instant")):
                        dateText = XmlUtil.text(dateElt)
                        if not GFMcontextDatePattern.match(dateText):
                            modelXbrl.uuidError("c030994905a54ac3ba51b8ba876469ca",
                                modelObject=dateElt, context=contextID, 
                                elementName=dateElt.prefixedName, value=dateText)
                #6.5.4 scenario
                hasSegment = XmlUtil.hasChild(context, XbrlConst.xbrli, "segment")
                hasScenario = XmlUtil.hasChild(context, XbrlConst.xbrli, "scenario")
                notAllowed = None
                if disclosureSystem.contextElement == "segment" and hasScenario:
                    notAllowed = _("Scenario")
                elif disclosureSystem.contextElement == "scenario" and hasSegment:
                    notAllowed = _("Segment")
                elif disclosureSystem.contextElement == "either" and hasSegment and hasScenario:
                    notAllowed = _("Both segment and scenario")
                elif disclosureSystem.contextElement == "none" and (hasSegment or hasScenario):
                    notAllowed = _("Neither segment nor scenario")
                if notAllowed:
                    modelXbrl.uuidError("ee343fbdd0d9487fbc60f78a093a948d",
                        modelObject=context, elementName=notAllowed, context=contextID)
        
                #6.5.5 segment only explicit dimensions
                for contextName in ("{http://www.xbrl.org/2003/instance}segment","{http://www.xbrl.org/2003/instance}scenario"):
                    for segScenElt in context.iterdescendants(contextName):
                        if isinstance(segScenElt,ModelObject):
                            childTags = ", ".join([child.prefixedName for child in segScenElt.iterchildren()
                                                   if isinstance(child,ModelObject) and 
                                                   child.tag != "{http://xbrl.org/2006/xbrldi}explicitMember"])
                            if len(childTags) > 0:
                                modelXbrl.uuidError("4ed8de4978744266ad5dd0811738e119",
                                                modelObject=context, context=contextID, content=childTags)
            del uniqueContextHashes
            self.modelXbrl.profileActivity("... filer context checks", minTimeToShow=1.0)
    
    
            #fact items from standard context (no dimension)
            amendmentDescription = None
            amendmentDescriptionFact = None
            amendmentFlag = None
            amendmentFlagFact = None
            documentPeriodEndDate = None
            documentType = None
            documentTypeFact = None
            deiItems = {}
            commonSharesItemsByStockClass = defaultdict(list)
            commonSharesClassMembers = None
            hasDefinedStockAxis = False
            hasUndefinedDefaultStockMember = False
            commonSharesClassUndefinedMembers = None
            commonStockMeasurementDatetime = None
    
            # parameter-provided CIKs and registrant names
            paramFilerIdentifier = None
            paramFilerIdentifiers = None
            paramFilerNames = None
            submissionType = None
            if self.validateEFM and self.parameters:
                p = self.parameters.get(ModelValue.qname("CIK",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    paramFilerIdentifier = p[1]
                p = self.parameters.get(ModelValue.qname("cikList",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    paramFilerIdentifiers = p[1].split(",")
                p = self.parameters.get(ModelValue.qname("cikNameList",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    paramFilerNames = p[1].split("|Edgar|")
                    if paramFilerIdentifiers and len(paramFilerIdentifiers) != len(paramFilerNames):
                        self.modelXbrl.uuidError("cc50dd1cf845427599493eccadeca155",
                            modelXbrl=modelXbrl, cikList=paramFilerIdentifiers, cikNameList=paramFilerNames)
                p = self.parameters.get(ModelValue.qname("submissionType",noPrefixIsNoNamespace=True))
                if p and len(p) == 2:
                    submissionType = p[1]
                        
            deiCheckLocalNames = {
                "EntityRegistrantName", 
                "EntityCommonStockSharesOutstanding",
                "EntityCurrentReportingStatus", 
                "EntityVoluntaryFilers", 
                disclosureSystem.deiCurrentFiscalYearEndDateElement, 
                "EntityFilerCategory", 
                "EntityWellKnownSeasonedIssuer", 
                "EntityPublicFloat", 
                disclosureSystem.deiDocumentFiscalYearFocusElement, 
                "DocumentFiscalPeriodFocus"
                 }
            #6.5.8 unused contexts
            for f in modelXbrl.facts:
                factContextID = f.contextID
                if factContextID in contextIDs:
                    contextIDs.remove(factContextID)
                    
                context = f.context
                factElementName = f.localName
                if disclosureSystem.deiNamespacePattern is not None:
                    factInDeiNamespace = disclosureSystem.deiNamespacePattern.match(f.namespaceURI)
                else:
                    factInDeiNamespace = None
                # standard dei items from required context
                if context is not None: # tests do not apply to tuples
                    if not context.hasSegment and not context.hasScenario: 
                        #default context
                        if factInDeiNamespace:
                            value = f.value
                            if factElementName == disclosureSystem.deiAmendmentFlagElement:
                                amendmentFlag = value
                                ammedmentFlagFact = f
                            elif factElementName == "AmendmentDescription":
                                amendmentDescription = value
                                amendmentDescriptionFact = f
                            elif factElementName == disclosureSystem.deiDocumentPeriodEndDateElement:
                                documentPeriodEndDate = value
                                commonStockMeasurementDatetime = context.endDatetime
                            elif factElementName == "DocumentType":
                                documentType = value
                                documentTypeFact = f
                            elif factElementName == disclosureSystem.deiFilerIdentifierElement:
                                deiItems[factElementName] = value
                                if entityIdentifierValue != value:
                                    self.modelXbrl.uuidError("c9dc9f19e8bd4115a9651d2486752ec5",
                                        modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                                        value=value, entityIdentifer=entityIdentifierValue)
                                if paramFilerIdentifier and value != paramFilerIdentifier:
                                    self.modelXbrl.uuidError("c9dc9f19e8bd4115a9651d2486752ec5",
                                        modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                                        value=value, filerIdentifer=paramFilerIdentifier)
                            elif factElementName == disclosureSystem.deiFilerNameElement:
                                deiItems[factElementName] = value
                                if paramFilerIdentifiers and paramFilerNames and entityIdentifierValue in paramFilerIdentifiers:
                                    prefix = paramFilerNames[paramFilerIdentifiers.index(entityIdentifierValue)]
                                    if not value.lower().startswith(prefix.lower()):
                                        self.modelXbrl.uuidError("cc50dd1cf845427599493eccadeca155",
                                            modelObject=f, elementName=disclosureSystem.deiFilerIdentifierElement,
                                            prefix=prefix, value=value)
                            elif factElementName in deiCheckLocalNames:
                                deiItems[factElementName] = value
                    else:
                        # segment present
                        isEntityCommonStockSharesOutstanding = factElementName == "EntityCommonStockSharesOutstanding"
                        hasClassOfStockMember = False
                        
                        # note all concepts used in explicit dimensions
                        for dimValue in context.qnameDims.values():
                            if dimValue.isExplicit:
                                dimConcept = dimValue.dimension
                                memConcept = dimValue.member
                                for dConcept in (dimConcept, memConcept):
                                    if dConcept is not None:
                                        conceptsUsed[dConcept] = False
                                if (isEntityCommonStockSharesOutstanding and
                                    dimConcept.name == "StatementClassOfStockAxis"):
                                    commonSharesItemsByStockClass[memConcept.qname].append(f)
                                    if commonSharesClassMembers is None:
                                        commonSharesClassMembers, hasDefinedStockAxis = self.getDimMembers(dimConcept)
                                    if not hasDefinedStockAxis: # no def LB for stock axis, note observed members
                                        commonSharesClassMembers.add(memConcept.qname) 
                                    hasClassOfStockMember = True
                                    
                        if isEntityCommonStockSharesOutstanding and not hasClassOfStockMember:
                            hasUndefinedDefaultStockMember = True   # absent dimension, may be no def LB
                #6.5.17 facts with precision
                concept = f.concept
                if concept is None:
                    modelXbrl.uuidError("b2ddd4c570254b40a113de0cb36e0429",
                        modelObject=f, fact=f.qname, contextID=factContextID)
                else:
                    # note fact concpts used
                    conceptsUsed[concept] = False
                    
                    if concept.isNumeric:
                        if f.precision:
                            modelXbrl.uuidError("991efba1de904f1c8fdead53069cc91e",
                                modelObject=f, fact=f.qname, contextID=factContextID, precision=f.precision)

                    #6.5.25 domain items as facts
                    if self.validateEFM and concept.type is not None and concept.type.isDomainItemType:
                        modelXbrl.uuidError("0a03d8a0d4ac42f49af76245d38221e7",
                            modelObject=f, fact=f.qname, contextID=factContextID)
    
                    
                if validateInlineXbrlGFM:
                    if f.localName == "nonFraction" or f.localName == "fraction":
                        syms = signOrCurrencyPattern.findall(f.text)
                        if syms:
                            modelXbrl.uuidError("ad57e8f8c9234f0789b0fa17b7085332",
                                modelObject=f, fact=f.qname, contextID=factContextID, 
                                value="".join(s for t in syms for s in t), text=f.text)
                            
            self.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)
    
            if len(contextIDs) > 0:
                modelXbrl.uuidError("62e9167018d047de96d62ab814936a2d",
                                modelXbrl=modelXbrl, contextIDs=", ".join(contextIDs))
    
            #6.5.9 start-end durations
            if disclosureSystem.GFM or \
               documentType in ('20-F', '40-F', '10-Q', '10-K', '10', 'N-CSR', 'N-CSRS', 'NCSR', 'N-Q'):
                '''
                for c1 in contexts:
                    if c1.isStartEndPeriod:
                        end1 = c1.endDatetime
                        start1 = c1.startDatetime
                        for c2 in contexts:
                            if c1 != c2 and c2.isStartEndPeriod:
                                duration = end1 - c2.startDatetime
                                if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                    modelXbrl.error(("EFM.6.05.09", "GFM.1.2.9"),
                                        _("Context {0} endDate and {1} startDate have a duration of one day; that is inconsistent with document type {2}."),
                                             c1.id, c2.id, documentType), 
                                        "err", )
                            if self.validateEFM and c1 != c2 and c2.isInstantPeriod:
                                duration = c2.endDatetime - start1
                                if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                    modelXbrl.error(
                                        _("Context {0} startDate and {1} end (instant) have a duration of one day; that is inconsistent with document type {2}."),
                                             c1.id, c2.id, documentType), 
                                        "err", "EFM.6.05.10")
                '''
                durationCntxStartDatetimes = defaultdict(list)
                for cntx in contexts:
                    if cntx.isStartEndPeriod:
                        durationCntxStartDatetimes[cntx.startDatetime].append(cntx)
                for cntx in contexts:
                    end = cntx.endDatetime
                    if cntx.isStartEndPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                for otherCntx in otherCntxs:
                                    if cntx != otherCntx:
                                        modelXbrl.uuidError("d300970043bc4b7d9d3630c7c425bb4c",
                                            modelObject=cntx, contextID=cntx.id, contextID2=otherCntx.id, documentType=documentType)
                    if self.validateEFM and cntx.isInstantPeriod:
                        for otherStart, otherCntxs in durationCntxStartDatetimes.items():
                            duration = end - otherStart
                            if duration > datetime.timedelta(0) and duration <= datetime.timedelta(1):
                                for otherCntx in otherCntxs:
                                    modelXbrl.uuidError("6639a6f8696648a5ba50eceef4480316",
                                        modelObject=cntx, contextID=cntx.id, contextID2=otherCntx.id, documentType=documentType)
                del durationCntxStartDatetimes
                self.modelXbrl.profileActivity("... filer instant-duration checks", minTimeToShow=1.0)
                
            #6.5.19 required context
            foundRequiredContext = False
            for c in contexts:
                if c.isStartEndPeriod:
                    if not c.hasSegment:
                        foundRequiredContext = True
                        break
            if not foundRequiredContext:
                modelXbrl.uuidError("a20a5bb5f1954cd2acd91cc0c61419e3",
                    modelObject=documentTypeFact, documentType=documentType)
                
            #6.5.11 equivalent units
            uniqueUnitHashes = {}
            for unit in self.modelXbrl.units.values():
                h = unit.hash
                if h in uniqueUnitHashes:
                    if unit.isEqualTo(uniqueUnitHashes[h]):
                        modelXbrl.uuidError("d9100047e33544b3ad8688d200365dfc",
                            modelObject=unit, unitID=unit.id, unitID2=uniqueUnitHashes[h].id)
                else:
                    uniqueUnitHashes[h] = unit
                if self.validateEFM:  # 6.5.38
                    for measureElt in unit.iterdescendants(tag="{http://www.xbrl.org/2003/instance}measure"):
                        if isinstance(measureElt.xValue, ModelValue.QName) and len(measureElt.xValue.localName) > 65:
                            l = len(measureElt.xValue.localName.encode("utf-8"))
                            if l > 200:
                                modelXbrl.uuidError("ad35a26eba4b4ea791e9692b09638ae5",
                                    modelObject=measureElt, measure=measureElt.xValue.localName, length=l)
            del uniqueUnitHashes
            self.modelXbrl.profileActivity("... filer unit checks", minTimeToShow=1.0)
   
    
            # EFM.6.05.14, GFM.1.02.13 xml:lang tests, as of v-17, full default lang is compared
            #if self.validateEFM:
            #    factLangStartsWith = disclosureSystem.defaultXmlLang[:2]
            #else:
            #    factLangStartsWith = disclosureSystem.defaultXmlLang
            requiredFactLang = disclosureSystem.defaultXmlLang

            #6.5.12 equivalent facts
            factsForLang = {}
            factForConceptContextUnitLangHash = {}
            keysNotDefaultLang = {}
            iF1 = 1
            for f1 in modelXbrl.facts:
                # build keys table for 6.5.14
                if not f1.isNil:
                    langTestKey = "{0},{1},{2}".format(f1.qname, f1.contextID, f1.unitID)
                    factsForLang.setdefault(langTestKey, []).append(f1)
                    lang = f1.xmlLang
                    if lang and lang != requiredFactLang: # not lang.startswith(factLangStartsWith):
                        keysNotDefaultLang[langTestKey] = f1
                        
                    if disclosureSystem.GFM and f1.isNumeric and \
                        f1.decimals and f1.decimals != "INF" and not f1.isNil:
                        try:
                            vf = float(f1.value)
                            vround = round(vf, int(f1.decimals))
                            if vf != vround: 
                                modelXbrl.uuidError("1df56581acdb4ae9a95a687c65dbb0eb",
                                    modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=vf, value2=vf - vround)
                        except (ValueError,TypeError):
                            modelXbrl.uuidError("1df56581acdb4ae9a95a687c65dbb0eb",
                                modelObject=f1, fact=f1.qname, contextID=f1.contextID, decimals=f1.decimals, value=f1.value)
                # 6.5.12 test
                h = f1.conceptContextUnitLangHash
                if h in factForConceptContextUnitLangHash:
                    f2 = factForConceptContextUnitLangHash[h]
                    if f1.qname == f2.qname and \
                       f1.contextID == f2.contextID and \
                       f1.unitID == f2.unitID and \
                       f1.xmlLang == f2.xmlLang:
                        modelXbrl.uuidError("7858743e2c004bd0be9ee4c9a05167f4",
                            modelObject=f1, fact=f1.qname, contextID=f1.contextID, contextID2=f2.contextID)
                else:
                    factForConceptContextUnitLangHash[h] = f1
                iF1 += 1
            del factForConceptContextUnitLangHash
            self.modelXbrl.profileActivity("... filer fact checks", minTimeToShow=1.0)
    
            #6.5.14 facts without english text
            for keyNotDefaultLang, factNotDefaultLang in keysNotDefaultLang.items():
                anyDefaultLangFact = False
                for fact in factsForLang[keyNotDefaultLang]:
                    if fact.xmlLang == requiredFactLang: #.startswith(factLangStartsWith):
                        anyDefaultLangFact = True
                        break
                if not anyDefaultLangFact:
                    self.modelXbrl.uuidError("aab70246cb544e3dbf583051ad9e17f1",
                        modelObject=factNotDefaultLang, fact=factNotDefaultLang.qname, contextID=factNotDefaultLang.contextID, 
                        lang=factNotDefaultLang.xmlLang, lang2=requiredFactLang) # factLangStartsWith)
                    
            #label validations
            if not labelsRelationshipSet:
                self.modelXbrl.uuidError("535dcc00edc9440b94117ebe1dffb271",
                    modelXbrl=modelXbrl)
            else:
                for concept in conceptsUsed.keys():
                    self.checkConceptLabels(modelXbrl, labelsRelationshipSet, disclosureSystem, concept)
                        
    
            #6.5.15 facts with xml in text blocks
            if self.validateEFMorGFM:
                ValidateFilingText.validateTextBlockFacts(modelXbrl)
            
                if amendmentFlag is None:
                    modelXbrl.uuidError("77e2af125a86465b82d477a638d9208a",
                        modelXbrl=modelXbrl, elementName=disclosureSystem.deiAmendmentFlagElement)
        
                if not documentPeriodEndDate:
                    modelXbrl.uuidError("77e2af125a86465b82d477a638d9208a",
                        modelXbrl=modelXbrl, elementName=disclosureSystem.deiDocumentPeriodEndDateElement)
                else:
                    dateMatch = datePattern.match(documentPeriodEndDate)
                    if not dateMatch or dateMatch.lastindex != 3:
                        modelXbrl.uuidError("3c6343cf07c4461a80bd6332306a3a8a",
                            modelXbrl=modelXbrl, elementName=disclosureSystem.deiDocumentPeriodEndDateElement,
                            date=documentPeriodEndDate)
            self.modelXbrl.profileActivity("... filer label and text checks", minTimeToShow=1.0)
    
            if self.validateEFM:
                if amendmentFlag == "true" and not amendmentDescription:
                    modelXbrl.uuidError("6636bdf7f5b042cb81d7935d56901ffa",
                        modelObject=amendmentFlagFact, contextID=amendmentFlagFact.contextID if amendmentFlagFact else "unknown")
        
                if amendmentDescription and ((not amendmentFlag) or amendmentFlag == "false"):
                    modelXbrl.uuidError("56d1640d9c4c484da4da402d70d794d2",
                        modelObject=amendmentDescriptionFact, contextID=amendmentDescriptionFact.contextID)
                    
                if not documentType:
                    modelXbrl.uuidError("602f0be3612e4c6cb5f93fd0a6701d72",
                        modelXbrl=modelXbrl)
                elif documentType not in {"10", "10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F", "6-K", "8-K", 
                                          "F-1", "F-10", "F-3", "F-4", "F-9", "S-1", "S-11", 
                                          "S-3", "S-4", "POS AM", "10-KT", "10-QT",
                                          "8-K/A", 
                                          "S-1/A", "S-11/A", "S-3/A", "S-4/A", 
                                          "10-KT/A", "10-QT/A",
                                          "485BPOS", "497 ", "NCSR", "N-CSR", "N-Q", 
                                          "N-Q/A",
                                          "Other"}:
                    modelXbrl.uuidError("8c4a49b67b354c7eb2d8629b20288bdf",
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType)
                elif submissionType:
                    expectedDocumentType = {
                            "10": "10", 
                            "10/A": "10", "10-K": "10-K", "10-K/A": "10-K", "10-Q": "10-Q", "10-Q/A": "10-Q", 
                            "20-F": "20-F", "20-F/A": "20-F", "40-F": "40-F", "40-F/A": "40-F", "485BPOS": "485BPOS", 
                            "6-K": "6-K", "6-K/A": "6-K", "8-K": "8-K", "F-1": "F-1", "F-1/A": "F-1", 
                            "F-10": "F-10", "F-10/A": "F-10", "F-3": "F-3", "F-3/A": "F-3", 
                            "F-4": "F-4", "F-4/A": "F-4", "F-9": "F-9", "F-9/A": "F-9", "N-1A": "N-1A", 
                            "NCSR": "NCSR", "NCSR/A": "NCSR", "NCSRS": "NCSR", "NCSRS/A": "NCSR", 
                            "N-Q": "N-Q", "N-Q/A": "N-Q", "S-1": "S-1", "S-1/A": "S-1", "S-11": "S-11", "S-11/A": "S-11", 
                            "S-3": "S-3", "S-3/A": "S-3", "S-4": "S-4", "S-4/A": "S-4", "N-CSR": "NCSR", "N-CSR/A": "NCSR", "N-CSRS": "NCSR", "NCSRS/A": "NCSR", 
                            "497": "Other", 
                            }.get(submissionType)
                    if expectedDocumentType and expectedDocumentType != documentType:
                        modelXbrl.uuidError("32bf176761a34b64bba2bb53160ff2fd",
                            modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType, submissionType=submissionType)
                    
                # 6.5.21
                for doctypesRequired, deiItemsRequired in (
                      (("10-K", "10-KT",
                        "10-Q", "10-QT",
                        "20-F",
                        "40-F",
                        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q",
                        "10", "S-1", "S-3", "S-4", "S-11", "POS AM",
                        "8-K", "F-1", "F-3", "F-10", "497", "485BPOS",
                        "Other"),
                        ("EntityRegistrantName", "EntityCentralIndexKey")),
                      (("10-K", "10-KT",
                        "20-F",
                        "40-F"),
                       ("EntityCurrentReportingStatus",)),
                     (("10-K", "10-KT",),
                      ("EntityVoluntaryFilers", "EntityPublicFloat")),
                      (("10-K", "10-KT",
                        "10-Q", "10-QT",
                        "20-F",
                        "40-F",
                        "6-K", "NCSR", "N-CSR", "N-CSRS", "N-Q"),
                        ("CurrentFiscalYearEndDate", "DocumentFiscalYearFocus", "DocumentFiscalPeriodFocus")),
                      (("10-K", "10-KT",
                        "10-Q", "10-QT",
                        "20-F",
                        "10", "S-1", "S-3", "S-4", "S-11", "POS AM"),
                        ("EntityFilerCategory",)),
                       (("10-K", "10-KT",
                         "20-F"),
                         ("EntityWellKnownSeasonedIssuer",))
                ):
                    if documentType in doctypesRequired:
                        for deiItem in deiItemsRequired:
                            if deiItem not in deiItems or deiItems[deiItem] == "":
                                modelXbrl.uuidError("865face2f5bd47e1a51aad138c4f3dd6",
                        modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType,
                        elementName=deiItem)
                                
                if documentType in ("10-K", "10-KT", "10-Q", "10-QT", "20-F", "40-F"):
                    defaultSharesOutstanding = deiItems.get("EntityCommonStockSharesOutstanding")
                    if commonSharesClassMembers:
                        if defaultSharesOutstanding:
                            modelXbrl.uuidError("8588aa3afd774333afdec10734e4514a",
                                modelObject=documentTypeFact, contextID=documentTypeFact.contextID, documentType=documentType)
                        elif len(commonSharesClassMembers) == 1 and not hasDefinedStockAxis:
                            modelXbrl.uuidError("b00a314e1e24441a8bb8552d1a5e03df",
                                modelObject=documentTypeFact, documentType=documentType)
                        missingClasses = commonSharesClassMembers - commonSharesItemsByStockClass.keys()
                        if missingClasses:
                            modelXbrl.uuidError("886c704c21ec4c63bdcfaa63cf05a5fe",
                                modelObject=documentTypeFact, documentType=documentType, stockClasses=", ".join([str(c) for c in missingClasses]))
                        for mem, facts in commonSharesItemsByStockClass.items():
                            if len(facts) != 1:
                                modelXbrl.uuidError("d2e6eb3b175e421383150278c3e4f4ff",
                                    modelObject=documentTypeFact, documentType=documentType, stockClasse=mem)
                            elif facts[0].context.instantDatetime != commonStockMeasurementDatetime:
                                modelXbrl.uuidError("b343db4ffb8d43fbb61c2f927a63c7fb",
                                    modelObject=documentTypeFact, documentType=documentType, stockClasse=mem, date=commonStockMeasurementDatetime)
                    elif hasUndefinedDefaultStockMember and not defaultSharesOutstanding:
                            modelXbrl.uuidError("7d44b4bd6eca4b76bd7141188d54a54a",
                                modelObject=documentTypeFact, documentType=documentType)
                    elif not defaultSharesOutstanding:
                        modelXbrl.uuidError("15b766c7d38546f084be16cbd5e2b3c9",
                            modelObject=documentTypeFact, documentType=documentType)
                
            elif disclosureSystem.GFM:
                for deiItem in (
                        disclosureSystem.deiCurrentFiscalYearEndDateElement, 
                        disclosureSystem.deiDocumentFiscalYearFocusElement, 
                        disclosureSystem.deiFilerNameElement):
                    if deiItem not in deiItems or deiItems[deiItem] == "":
                        modelXbrl.uuidError("018674272f154533a06f6b2253b3b8aa",
                            modelXbrl=modelXbrl, elementName=deiItem)
            self.modelXbrl.profileActivity("... filer required facts checks", minTimeToShow=1.0)
    
            #6.5.27 footnote elements, etc
            footnoteLinkNbr = 0
            for footnoteLinkElt in xbrlInstDoc.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}footnoteLink"):
                if isinstance(footnoteLinkElt,ModelObject):
                    footnoteLinkNbr += 1
                    
                    linkrole = footnoteLinkElt.get("{http://www.w3.org/1999/xlink}role")
                    if linkrole != XbrlConst.defaultLinkRole:
                        modelXbrl.uuidError("0c949a7b23cf40d8835e9dbc83588832",
                            modelObject=footnoteLinkElt, footnoteLinkNumber=footnoteLinkNbr, linkrole=linkrole)
        
                    # find modelLink of this footnoteLink
                    modelLink = modelXbrl.baseSetModelLink(footnoteLinkElt)
                    relationshipSet = modelXbrl.relationshipSet("XBRL-footnotes", linkrole)
                    if (modelLink is None) or (not relationshipSet):
                        continue    # had no child elements to parse
                    locNbr = 0
                    arcNbr = 0
                    for child in footnoteLinkElt.getchildren():
                        if isinstance(child,ModelObject):
                            xlinkType = child.get("{http://www.w3.org/1999/xlink}type")
                            if child.namespaceURI != XbrlConst.link or \
                               xlinkType not in ("locator", "resource", "arc") or \
                               child.localName not in ("loc", "footnote", "footnoteArc"):
                                    modelXbrl.uuidError("b5231aaaeab9437cb79fb9144241b5c2",
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, elementName=child.prefixedName)
                            elif xlinkType == "locator":
                                locNbr += 1
                                locrole = child.get("{http://www.w3.org/1999/xlink}role")
                                if locrole is not None and (disclosureSystem.GFM or \
                                                            not disclosureSystem.uriAuthorityValid(locrole)): 
                                    modelXbrl.uuidError("bd44aad8badc4e4383ade87682b5fd50",
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, 
                                        locNumber=locNbr, role=locrole)
                                href = child.get("{http://www.w3.org/1999/xlink}href")
                                if not href.startswith("#"): 
                                    modelXbrl.uuidError("7b5449c0845e4cd48d5f30655600903b",
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, locNumber=locNbr, locHref=href)
                                else:
                                    label = child.get("{http://www.w3.org/1999/xlink}label")
                            elif xlinkType == "arc":
                                arcNbr += 1
                                arcrole = child.get("{http://www.w3.org/1999/xlink}arcrole")
                                if (self.validateEFM and not disclosureSystem.uriAuthorityValid(arcrole)) or \
                                   (disclosureSystem.GFM  and arcrole != XbrlConst.factFootnote and arcrole != XbrlConst.factExplanatoryFact): 
                                    modelXbrl.uuidError("6b64e3529b074af6b619985020f32e2d",
                                        modelObject=child, footnoteLinkNumber=footnoteLinkNbr, arcNumber=arcNbr, arcrole=arcrole)
                            elif xlinkType == "resource": # footnote
                                footnoterole = child.get("{http://www.w3.org/1999/xlink}role")
                                if footnoterole == "":
                                    modelXbrl.uuidError("a35fbbd215964da18f0b0fa5fd636825",
                                        modelObject=child, xlinkLabel=child.get("{http://www.w3.org/1999/xlink}label"))
                                elif (self.validateEFM and not disclosureSystem.uriAuthorityValid(footnoterole)) or \
                                     (disclosureSystem.GFM  and footnoterole != XbrlConst.footnote): 
                                    modelXbrl.uuidError("13cc954833d54735b6b01f40dc5ea3f0",
                                        modelObject=child, xlinkLabel=child.get("{http://www.w3.org/1999/xlink}label"),
                                        role=footnoterole)
                                if self.validateEFM:
                                    ValidateFilingText.validateFootnote(modelXbrl, child)
                                # find modelResource for this element
                                foundFact = False
                                if XmlUtil.text(child) != "":
                                    for relationship in relationshipSet.toModelObject(child):
                                        if isinstance(relationship.fromModelObject, ModelFact):
                                            foundFact = True
                                            break
                                    if not foundFact:
                                        modelXbrl.uuidError("df4a2ddb81544b8e81fb264721db3729",
                                            modelObject=child, footnoteLinkNumber=footnoteLinkNbr, 
                                            xlinkLabel=child.get("{http://www.w3.org/1999/xlink}label"))
            self.modelXbrl.profileActivity("... filer rfootnotes checks", minTimeToShow=1.0)

        # entry point schema checks
        elif modelXbrl.modelDocument.type == ModelDocument.Type.SCHEMA:
            if self.validateSBRNL:
                # entry must have a P-link
                if not any(hrefElt.localName == "linkbaseRef" and hrefElt.get("{http://www.w3.org/1999/xlink}role") == "http://www.xbrl.org/2003/role/presentationLinkbaseRef"
                           for hrefElt, hrefDoc, hrefId in modelXbrl.modelDocument.hrefObjects):
                    modelXbrl.uuidError("eda1ec1fd28c47908d20ad46ce617609",
                        modelObject=modelXbrl.modelDocument)
        # all-labels and references checks
        defaultLangStandardLabels = {}
        for concept in modelXbrl.qnameConcepts.values():
            conceptHasDefaultLangStandardLabel = False
            for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
                modelLabel = modelLabelRel.toModelObject
                role = modelLabel.role
                text = modelLabel.text
                lang = modelLabel.xmlLang
                if role == XbrlConst.documentationLabel:
                    if concept.modelDocument.targetNamespace in disclosureSystem.standardTaxonomiesDict:
                        modelXbrl.uuidError("3269d06d4a564c3f813e475234eef183",
                            modelObject=modelLabel, concept=concept.qname, text=text)
                elif text and lang and lang.startswith(disclosureSystem.defaultXmlLang):
                    if role == XbrlConst.standardLabel:
                        if text in defaultLangStandardLabels:
                            modelXbrl.uuidError("485197f7d7ec414086b3ef68101dc29a",
                                modelObject=modelLabel, concept=concept.qname, 
                                concept2=defaultLangStandardLabels[text].qname, 
                                lang=disclosureSystem.defaultLanguage, text=text[:80])
                        else:
                            defaultLangStandardLabels[text] = concept
                        conceptHasDefaultLangStandardLabel = True
                    if len(text) > 511:
                        modelXbrl.uuidError("899cf0552574497da30d6a9050e790ed",
                            modelObject=modelLabel, concept=concept.qname, role=role, length=len(text), text=text[:80])
                    match = modelXbrl.modelManager.disclosureSystem.labelCheckPattern.search(text)
                    if match:
                        modelXbrl.uuidError("899cf0552574497da30d6a9050e790ed",
                            modelObject=modelLabel, concept=concept.qname, role=role, text=match.group())
                if text is not None and len(text) > 0 and \
                   (modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[0]) or \
                    modelXbrl.modelManager.disclosureSystem.labelTrimPattern.match(text[-1])):
                    modelXbrl.uuidError("f026aa1c34014ee9b05be4f45031c7cc",
                        modelObject=modelLabel, concept=concept.qname, role=role, lang=lang, text=text)
            for modelRefRel in referencesRelationshipSetWithProhibits.fromModelObject(concept):
                modelReference = modelRefRel.toModelObject
                text = modelReference.text
                #6.18.1 no reference to company extension concepts
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    modelXbrl.uuidError("fd0ea2541a3c42f2a7113ef105c5abbc",
                        modelObject=modelReference, concept=concept.qname, text=text)
                elif (self.validateEFM or self.validateSBRNL) and not isStandardUri(modelRefRel.modelDocument.uri): 
                    #6.18.2 no extension to add or remove references to standard concepts
                    modelXbrl.uuidError("e1d99e17b8c74cd2ba23a2fa0620f328",
                        modelObject=modelReference, concept=concept.qname, text=text)
            if self.validateSBRNL and (concept.isItem or concept.isTuple):
                if concept.modelDocument.targetNamespace not in disclosureSystem.standardTaxonomiesDict:
                    if not conceptHasDefaultLangStandardLabel:
                        modelXbrl.uuidError("e44d36b573db4be4b56c05fdb6b96e77",
                            modelObject=concept, concept=concept.qname)
                    subsGroup = concept.get("substitutionGroup")
                    if ((not concept.isAbstract or subsGroup == "sbr:presentationItem") and
                        not (presentationRelationshipSet.toModelObject(concept) or
                             presentationRelationshipSet.fromModelObject(concept))):
                        modelXbrl.uuidError("9e3daa7acbfd447b9b25010b15f073f6",
                            modelObject=concept, concept=concept.qname)
                    elif ((concept.isDimensionItem or
                          (subsGroup and (subsGroup.endswith(":domainItem") or subsGroup.endswith(":domainMemberItem")))) and
                        not (presentationRelationshipSet.toModelObject(concept) or
                             presentationRelationshipSet.fromModelObject(concept))):
                        modelXbrl.uuidError("1d737554be2f4ffebfc9061f3208c69f",
                            modelObject=concept, concept=concept.qname)
                    if (concept.substitutionGroupQname and 
                        concept.substitutionGroupQname.namespaceURI not in disclosureSystem.baseTaxonomyNamespaces):
                        modelXbrl.uuidError("c4d77921c19e4e48ac2f24c3e875310d",
                            modelObject=concept, concept=concept.qname)
                            
                    if concept.isTuple: # verify same presentation linkbase nesting
                        pLinkedQnames = set(rel.toModelObject.qname
                                            for rel in modelXbrl.relationshipSet(XbrlConst.parentChild).fromModelObject(concept)
                                            if rel.toModelObject is not None)
                        for missingQname in set(concept.type.elements) ^ pLinkedQnames:
                            modelXbrl.uuidError("7e710fc3cef542b9af840507f3e4cea9",
                                modelObject=concept, concept=concept.qname, missingQname=missingQname)
                self.checkConceptLabels(modelXbrl, labelsRelationshipSet, disclosureSystem, concept)
                self.checkConceptLabels(modelXbrl, genLabelsRelationshipSet, disclosureSystem, concept)

        if self.validateSBRNL:
            for qname, modelType in modelXbrl.qnameTypes.items():
                if qname.namespaceURI not in disclosureSystem.baseTaxonomyNamespaces:
                    facets = modelConcept.facets
                    if facets:
                        if facets.keys() & {"minLength", "maxLength"}:
                            modelXbrl.uuidError("baacd17630f74f0196e8f01052454f15",
                                modelObject=modelType, typename=modelType.qname)
                        if "enumeration" in facets and modelConcept.baseXsdType != "string":
                            modelXbrl.uuidError("720b09e1f3834837a8c20421e68335b7",
                                modelObject=modelType, concept=modelType.qname)
                        
        self.modelXbrl.profileActivity("... filer concepts checks", minTimeToShow=1.0)

        defaultLangStandardLabels = None #dereference
        
        ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
        if self.validateSBRNL: # build camelCasedNamesTable
            self.nameWordsTable = {}
            for name in modelXbrl.nameConcepts.keys():
                words = []
                wordChars = []
                lastchar = ""
                for c in name:
                    if c.isupper() and lastchar.islower(): # it's another word
                        partialName = ''.join(wordChars)
                        if partialName in modelXbrl.nameConcepts:
                            words.append(partialName)
                    wordChars.append(c)
                    lastchar = c
                if words:
                    self.nameWordsTable[name] = words
            self.modelXbrl.profileActivity("... build name words table", minTimeToShow=1.0)
        '''
        
        # checks on all documents: instance, schema, instance                                
        ValidateFilingDTS.checkDTS(self, modelXbrl.modelDocument, [])
        ''' removed RH 2011-12-23, corresponding use of nameWordsTable in ValidateFilingDTS
        if self.validateSBRNL:
            del self.nameWordsTable
        '''
        self.modelXbrl.profileActivity("... filer DTS checks", minTimeToShow=1.0)

        # checks for namespace clashes
        if self.validateEFM:
            # check number of us-roles taxonomies referenced
            for nsPattern in (usTypesPattern, usRolesPattern, usDeiPattern):
                usTypesURIs = set(ns for ns in modelXbrl.namespaceDocs.keys() if nsPattern.match(ns))
                if len(usTypesURIs) > 1:
                    modelXbrl.uuidError("10e9b4315062431e8830e7db2bdb68ee",
                        modelObject=modelXbrl, namespaceConflicts=usTypesURIs)
            
        conceptsUsedWithPreferredLabels = defaultdict(list)
        usedCalcsPresented = defaultdict(set) # pairs of concepts objectIds used in calc
        drsELRs = set()
        
        # do calculation, then presentation, then other arcroles
        for arcroleFilter in (XbrlConst.summationItem, XbrlConst.parentChild, "*"):
            for baseSetKey, baseSetModelLinks  in modelXbrl.baseSets.items():
                arcrole, ELR, linkqname, arcqname = baseSetKey
                if ELR and not arcrole.startswith("XBRL-"):
                    # assure summationItem, then parentChild, then others
                    if not (arcroleFilter == arcrole or
                            arcroleFilter == "*" and arcrole not in (XbrlConst.summationItem, XbrlConst.parentChild)):
                        continue
                    if self.validateEFMorGFM or (self.validateSBRNL and arcrole == XbrlConst.parentChild):
                        ineffectiveArcs = ModelRelationshipSet.ineffectiveArcs(baseSetModelLinks, arcrole)
                        #validate ineffective arcs
                        for modelRel in ineffectiveArcs:
                            if modelRel.fromModelObject is not None and modelRel.toModelObject is not None:
                                self.modelXbrl.uuidError("0ab48559bb1d444398d1e70209dfef0b",
                                    modelObject=modelRel, arc=modelRel.qname, linkrole=modelRel.linkrole, arcrole=modelRel.arcrole,
                                    conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                                    ineffectivity=modelRel.ineffectivity)
                    if arcrole == XbrlConst.parentChild:
                        conceptsPresented = set()
                        localPreferredLabels = defaultdict(set)
                        # 6.12.2 check for distinct order attributes
                        for relFrom, rels in modelXbrl.relationshipSet(arcrole, ELR).fromModelObjects().items():
                            targetConceptPreferredLabels = defaultdict(set)
                            orderRels = {}
                            firstRel = True
                            relFromUsed = True
                            for rel in rels:
                                if firstRel:
                                    firstRel = False
                                    if relFrom in conceptsUsed:
                                        conceptsUsed[relFrom] = True # 6.12.3, has a pres relationship
                                        relFromUsed = True
                                relTo = rel.toModelObject
                                preferredLabel = rel.preferredLabel
                                if relTo in conceptsUsed:
                                    conceptsUsed[relTo] = True # 6.12.3, has a pres relationship
                                    if preferredLabel and preferredLabel != "":
                                        conceptsUsedWithPreferredLabels[relTo].append(preferredLabel)
                                        if self.validateSBRNL and preferredLabel in ("periodStart","periodEnd"):
                                            self.modelXbrl.uuidError("d5954c9011ae40c6904e443dcb15d364",
                                                modelObject=modelRel)
                                    # 6.12.5 distinct preferred labels in base set
                                    preferredLabels = targetConceptPreferredLabels[relTo]
                                    if (preferredLabel in preferredLabels or
                                        (self.validateSBRNL and not relFrom.isTuple and
                                         (not preferredLabel or None in preferredLabels))):
                                        self.modelXbrl.uuidError("2a8a2bebfbe74c69b4afbadad1bfaef4",
                                            modelObject=rel, concept=relTo.qname, preferredLabel=preferredLabel, linkrole=rel.linkrole)
                                    else:
                                        preferredLabels.add(preferredLabel)
                                    if relFromUsed:
                                        # 6.14.5
                                        conceptsPresented.add(relFrom.objectIndex)
                                        conceptsPresented.add(relTo.objectIndex)
                                order = rel.order
                                if order in orderRels:
                                    self.modelXbrl.uuidError("fef5fd010bdd4285b3cf6e521e6a2320",
                                        modelObject=rel, conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                        conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                else:
                                    orderRels[order] = rel
                                if self.validateSBRNL and not relFrom.isTuple:
                                    if relTo in localPreferredLabels:
                                        if {None, preferredLabel} & localPreferredLabels[relTo]:
                                            self.modelXbrl.uuidError("387af295f70a44f9983a4fc0db9715d1",
                                                modelObject=rel, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=relTo.qname)
                                    localPreferredLabels[relTo].add(preferredLabel)
                        for conceptPresented in conceptsPresented:
                            if conceptPresented in usedCalcsPresented:
                                usedCalcPairingsOfConcept = usedCalcsPresented[conceptPresented]
                                if len(usedCalcPairingsOfConcept & conceptsPresented) > 0:
                                    usedCalcPairingsOfConcept -= conceptsPresented
                    elif arcrole == XbrlConst.summationItem:
                        if self.validateEFMorGFM:
                            # 6.14.3 check for relation concept periods
                            fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                            for relFrom, rels in fromRelationships.items():
                                orderRels = {}
                                for rel in rels:
                                    relTo = rel.toModelObject
                                    # 6.14.03 must have matched period types across relationshp
                                    if relFrom.periodType != relTo.periodType:
                                        self.modelXbrl.uuidError("8e313883480348d18cfef2a9e00f876f",
                                            modelObject=rel, linkrole=rel.linkrole, conceptFrom=relFrom.qname, conceptTo=relTo.qname)
                                    # 6.14.5 concepts used must have pres in same ext link
                                    if relFrom in conceptsUsed and relTo in conceptsUsed:
                                        fromObjId = relFrom.objectIndex
                                        toObjId = relTo.objectIndex
                                        if fromObjId < toObjId:
                                            usedCalcsPresented[fromObjId].add(toObjId)
                                        else:
                                            usedCalcsPresented[toObjId].add(fromObjId)
                                            
                                    order = rel.order
                                    if order in orderRels and disclosureSystem.GFM:
                                        self.modelXbrl.uuidError("26440b9dcafe4df8b13d4fff00200cc0",
                                            modelObject=rel, linkrole=rel.linkrole, conceptFrom=relFrom.qname, order=order,
                                            conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                    else:
                                        orderRels[order] = rel
                                if self.directedCycle(relFrom,relFrom,fromRelationships):
                                    self.modelXbrl.uuidError("4c1b5b040a8b4415b550369a71913e2f",
                                        modelObject=rels[0], linkrole=ELR, concept=relFrom.qname)
                        elif self.validateSBRNL:
                            # find a calc relationship to get the containing document name
                            for modelRel in self.modelXbrl.relationshipSet(arcrole, ELR).modelRelationships:
                                self.modelXbrl.uuidError("8c0be7add8d74429b9bf66c9ac0f12b0",
                                    modelObject=modelRel, linkrole=ELR)
                                break
                                
                    elif arcrole == XbrlConst.all or arcrole == XbrlConst.notAll:
                        drsELRs.add(ELR)
                        
                    elif arcrole == XbrlConst.dimensionDomain or arcrole == XbrlConst.dimensionDefault and \
                         self.validateEFMorGFM:
                        # 6.16.3 check domain targets in extension linkbases are domain items
                        fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                        for relFrom, rels in fromRelationships.items():
                            for rel in rels:
                                relTo = rel.toModelObject
    
                                if not (relTo.type is not None and relTo.type.isDomainItemType) and not isStandardUri(rel.modelDocument.uri):
                                    self.modelXbrl.uuidError("cc614e3611b34ac6b536d391b6effd6e",
                                        modelObject=rel, conceptFrom=relFrom.qname, conceptTo=relTo.qname, linkrole=rel.linkrole)

                    elif self.validateSBRNL:
                        if arcrole == XbrlConst.dimensionDefault:
                            for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                                self.modelXbrl.uuidError("cfa70ede79344b049d9ae157e09f00be",
                                    modelObject=modelRel, conceptFrom=modelRel.fromModelObject.qname, conceptTo=modelRel.toModelObject.qname, 
                                    linkrole=modelRel.linkrole)
                        if not (XbrlConst.isStandardArcrole(arcrole) or XbrlConst.isDefinitionOrXdtArcrole(arcrole)):
                            for modelRel in self.modelXbrl.relationshipSet(arcrole).modelRelationships:
                                relTo = modelRel.toModelObject
                                relFrom = modelRel.fromModelObject
                                if not ((isinstance(relFrom,ModelConcept) and isinstance(relTo,ModelConcept)) or
                                        (relFrom.modelDocument.inDTS and
                                         (relTo.qname == XbrlConst.qnGenLabel and modelRel.arcrole == XbrlConst.elementLabel) or
                                         (relTo.qname == XbrlConst.qnGenReference and modelRel.arcrole == XbrlConst.elementReference) or
                                         (relTo.qname == self.qnSbrLinkroleorder))):
                                    self.modelXbrl.uuidError("dc8ed579ce944da7b72b9758f24b7f3e",
                                        modelObject=modelRel, elementFrom=relFrom.qname, elementTo=relTo.qname, 
                                        linkrole=modelRel.linkrole, arcrole=arcrole)
                            
                           
                    # definition tests (GFM only, for now)
                    if XbrlConst.isDefinitionOrXdtArcrole(arcrole) and disclosureSystem.GFM: 
                        fromRelationships = modelXbrl.relationshipSet(arcrole,ELR).fromModelObjects()
                        for relFrom, rels in fromRelationships.items():
                            orderRels = {}
                            for rel in rels:
                                relTo = rel.toModelObject
                                order = rel.order
                                if order in orderRels and disclosureSystem.GFM:
                                    self.modelXbrl.uuidError("e48f696cf8b64946a84ad77d966281e1",
                                        modelObject=rel, conceptFrom=relFrom.qname, order=order, linkrole=rel.linkrole, 
                                        conceptTo=rel.toModelObject.qname, conceptTo2=orderRels[order].toModelObject.qname)
                                else:
                                    orderRels[order] = rel
                                if (arcrole not in (XbrlConst.dimensionDomain, XbrlConst.domainMember) and
                                    rel.get("{http://xbrl.org/2005/xbrldt}usable") == "false"):
                                    self.modelXrl.uuidError("0f88a16360684fa5860b600c14380804",
                                        modelObject=rel, arc=rel.qname, conceptFrom=relFrom.qname, linkrole=rel.linkrole, conceptTo=rel.toModelObject.qname)

        self.modelXbrl.profileActivity("... filer relationships checks", minTimeToShow=1.0)

                                
        # checks on dimensions
        ValidateFilingDimensions.checkDimensions(self, drsELRs)
        self.modelXbrl.profileActivity("... filer dimensions checks", minTimeToShow=1.0)
                                        
        for concept, hasPresentationRelationship in conceptsUsed.items():
            if not hasPresentationRelationship:
                self.modelXbrl.uuidError("7f9bebfa2c82446dbfbf68b49d00f17c",
                    modelObject=concept, concept=concept.qname)
                
        for fromIndx, toIndxs in usedCalcsPresented.items():
            for toIndx in toIndxs:
                self.modelXbrl.uuidError("aefaaf42d834489b8da6d4e91021d954",
                    modelObject=self.modelXbrl.modelObject(fromIndx), conceptFrom=self.modelXbrl.modelObject(fromIndx).qname, conceptTo=self.modelXbrl.modelObject(toIndx).qname)
                
        for concept, preferredLabels in conceptsUsedWithPreferredLabels.items():
            for preferredLabel in preferredLabels:
                hasDefaultLangPreferredLabel = False
                for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
                    modelLabel = modelLabelRel.toModelObject
                    if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
                       modelLabel.role == preferredLabel:
                        hasDefaultLangPreferredLabel = True
                        break
                if not hasDefaultLangPreferredLabel:
                    self.modelXbrl.uuidError("ddd26e7f4eea4f44ad5e236f64b1fd6c",
                        modelObject=concept, concept=concept.qname, 
                        lang=disclosureSystem.defaultLanguage, preferredLabel=preferredLabel)
                
        # 6 16 4, 1.16.5 Base sets of Domain Relationship Sets testing
        self.modelXbrl.profileActivity("... filer preferred label checks", minTimeToShow=1.0)

        if self.validateSBRNL:
            # check presentation link roles for generic linkbase order number
            ordersRelationshipSet = modelXbrl.relationshipSet("http://www.nltaxonomie.nl/2011/arcrole/linkrole-order")
            presLinkroleNumberURI = {}
            presLinkrolesCount = 0
            for countLinkroles in (True, False):
                for roleURI, modelRoleTypes in modelXbrl.roleTypes.items():
                    for modelRoleType in modelRoleTypes:
                        if XbrlConst.qnLinkPresentationLink in modelRoleType.usedOns:
                            if countLinkroles:
                                presLinkrolesCount += 1
                            else:
                                if not ordersRelationshipSet:
                                    modelXbrl.uuidError("2f51e4433b6949ffba425d055a66bc8a",
                                        modelObject=modelRoleType, linkrole=modelRoleType.roleURI)
                                else:
                                    order = None
                                    for orderNumRel in ordersRelationshipSet.fromModelObject(modelRoleType):
                                        order = orderNumRel.toModelObject.xValue
                                        if order in presLinkroleNumberURI:
                                            modelXbrl.uuidError("a45dc872fc2a45afba0ec2713a8aa9f5",
                                                modelObject=modelRoleType, order=order, linkrole=modelRoleType.roleURI, otherLinkrole=presLinkroleNumberURI[order])
                                        else:
                                            presLinkroleNumberURI[order] = modelRoleType.roleURI
                                    if not order:
                                        modelXbrl.uuidError("aa84e36482e74c4199f4816574ea08e7",
                                            modelObject=modelRoleType, linkrole=modelRoleType.roleURI)
                if countLinkroles and presLinkrolesCount < 2:
                    break   # don't check order numbers if only one presentation linkrole
            # check arc role definitions for labels
            for arcroleURI, modelRoleTypes in modelXbrl.arcroleTypes.items():
                for modelRoleType in modelRoleTypes:
                    if not arcroleURI.startswith("http://xbrl.org/") and (
                       not modelRoleType.genLabel(lang="nl") or not modelRoleType.genLabel(lang="en")):
                        modelXbrl.uuidError("63fcf11b8a0d401cb5023c5551729f61",
                            modelObject=modelRoleType, arcrole=arcroleURI)

            for modelType in modelXbrl.qnameTypes.values():
                if (modelType.modelDocument.targetNamespace not in disclosureSystem.baseTaxonomyNamespaces and
                    modelType.facets and 
                    "enumeration" in modelType.facets and
                    not modelType.isDerivedFrom(XbrlConst.qnXbrliStringItemType)):
                    modelXbrl.uuidError("720b09e1f3834837a8c20421e68335b7",
                                    modelObject=modelType, value=modelType.qname)
            self.modelXbrl.profileActivity("... SBR role types and type facits checks", minTimeToShow=1.0)
        modelXbrl.modelManager.showStatus(_("ready"), 2000)
                    
    def directedCycle(self, relFrom, origin, fromRelationships):
        if relFrom in fromRelationships:
            for rel in fromRelationships[relFrom]:
                relTo = rel.toModelObject
                if relTo == origin or self.directedCycle(relTo, origin, fromRelationships):
                    return True
        return False
    
    def getDimMembers(self, dim, default=None, rels=None, members=None, visited=None):
        hasDefinedRelationship = False
        if rels is None: 
            visited = set()
            members = set()
            for rel in self.modelXbrl.relationshipSet(XbrlConst.dimensionDefault).fromModelObject(dim):
                default = rel.toModelObject
            rels = self.modelXbrl.relationshipSet(XbrlConst.dimensionDomain).fromModelObject(dim)
        for rel in rels:
            hasDefinedRelationship = True
            relTo = rel.toModelObject
            if rel.isUsable and relTo != default:
                members.add(relTo.qname)
            toELR = rel.targetRole
            if not toELR: toELR = rel.linkrole
            if relTo not in visited:
                visited.add(relTo)
                domMbrRels = self.modelXbrl.relationshipSet(XbrlConst.domainMember, toELR).fromModelObject(relTo)
                self.getDimMembers(dim, default, domMbrRels, members, visited)
                visited.discard(relTo)
        return (members,hasDefinedRelationship)   

    def checkConceptLabels(self, modelXbrl, labelsRelationshipSet, disclosureSystem, concept):
        hasDefaultLangStandardLabel = False
        dupLabels = set()
        for modelLabelRel in labelsRelationshipSet.fromModelObject(concept):
            modelLabel = modelLabelRel.toModelObject
            if modelLabel is not None and modelLabel.xmlLang:
                if modelLabel.xmlLang.startswith(disclosureSystem.defaultXmlLang) and \
                   modelLabel.role == XbrlConst.standardLabel:
                    hasDefaultLangStandardLabel = True
                dupDetectKey = ( (modelLabel.role or ''), modelLabel.xmlLang)
                if dupDetectKey in dupLabels:
                    modelXbrl.uuidError("e7d55a98a1b04d0194f3a8b5ccc3fbdb",
                        modelObject=concept, concept=concept.qname, 
                        role=dupDetectKey[0], lang=dupDetectKey[1])
                else:
                    dupLabels.add(dupDetectKey)
                
        #6 10.1 en-US standard label
        if not hasDefaultLangStandardLabel:
            modelXbrl.uuidError("ef8ce23a52234e5a867c9e1118e701bc",
                modelObject=concept, concept=concept.qname, 
                lang=disclosureSystem.defaultLanguage)
            
        #6 10.3 default lang label for every role
        try:
            dupLabels.add(("zzzz",disclosureSystem.defaultXmlLang)) #to allow following loop
            priorRole = None
            hasDefaultLang = True
            for role, lang in sorted(dupLabels):
                if role != priorRole:
                    if not hasDefaultLang:
                        modelXbrl.uuidError("cec6925f337341019fce9977293078d1",
                            modelObject=concept, concept=concept.qname, 
                            lang=disclosureSystem.defaultLanguage, role=priorRole)
                    hasDefaultLang = False
                    priorRole = role
                if lang is not None and lang.startswith(disclosureSystem.defaultXmlLang):
                    hasDefaultLang = True
        except Exception as err:
            pass
