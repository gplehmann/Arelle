'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import re
from arelle import (ModelDocument, XmlUtil, XbrlUtil, XbrlConst, 
                ValidateXbrlCalcs, ValidateXbrlDimensions, ValidateXbrlDTS, ValidateFormula, ValidateUtr)
from arelle.ModelObject import ModelObject
from arelle.ModelInstanceObject import ModelInlineFact
from arelle.ModelValue import qname

arcNamesTo21Resource = {"labelArc","referenceArc"}
xlinkTypeValues = {None, "simple", "extended", "locator", "arc", "resource", "title", "none"}
xlinkActuateValues = {None, "onLoad", "onRequest", "other", "none"}
xlinkShowValues = {None, "new", "replace", "embed", "other", "none"}
xlinkLabelAttributes = {"{http://www.w3.org/1999/xlink}label", "{http://www.w3.org/1999/xlink}from", "{http://www.w3.org/1999/xlink}to"}
periodTypeValues = {"instant","duration"}
balanceValues = {None, "credit","debit"}
baseXbrliTypes = {
        "decimalItemType", "floatItemType", "doubleItemType", "integerItemType",
        "nonPositiveIntegerItemType", "negativeIntegerItemType", "longItemType", "intItemType",
        "shortItemType", "byteItemType", "nonNegativeIntegerItemType", "unsignedLongItemType",
        "unsignedIntItemType", "unsignedShortItemType", "unsignedByteItemType",
        "positiveIntegerItemType", "monetaryItemType", "sharesItemType", "pureItemType",
        "fractionItemType", "stringItemType", "booleanItemType", "hexBinaryItemType",
        "base64BinaryItemType", "anyURIItemType", "QNameItemType", "durationItemType",
        "dateTimeItemType", "timeItemType", "dateItemType", "gYearMonthItemType",
        "gYearItemType", "gMonthDayItemType", "gDayItemType", "gMonthItemType",
        "normalizedStringItemType", "tokenItemType", "languageItemType", "NameItemType", "NCNameItemType"
      }

class ValidateXbrl:
    def __init__(self, testModelXbrl):
        self.testModelXbrl = testModelXbrl
        
    def close(self, reusable=True):
        if reusable:
            testModelXbrl = self.testModelXbrl
        self.__dict__.clear()   # dereference everything
        if reusable:
            self.testModelXbrl = testModelXbrl
        
    def validate(self, modelXbrl, parameters=None):
        self.parameters = parameters
        self.precisionPattern = re.compile("^([0-9]+|INF)$")
        self.decimalsPattern = re.compile("^(-?[0-9]+|INF)$")
        self.isoCurrencyPattern = re.compile(r"^[A-Z]{3}$")
        self.modelXbrl = modelXbrl
        self.validateDisclosureSystem = modelXbrl.modelManager.validateDisclosureSystem
        self.disclosureSystem = modelXbrl.modelManager.disclosureSystem
        self.validateEFM = self.validateDisclosureSystem and self.disclosureSystem.EFM
        self.validateGFM = self.validateDisclosureSystem and self.disclosureSystem.GFM
        self.validateEFMorGFM = self.validateDisclosureSystem and self.disclosureSystem.EFMorGFM
        self.validateHMRC = self.validateDisclosureSystem and self.disclosureSystem.HMRC
        self.validateSBRNL = self.validateDisclosureSystem and self.disclosureSystem.SBRNL
        self.validateXmlLang = self.validateDisclosureSystem and self.disclosureSystem.xmlLangPattern
        self.validateCalcLB = modelXbrl.modelManager.validateCalcLB
        self.validateInferDecimals = modelXbrl.modelManager.validateInferDecimals
        
        # xlink validation
        modelXbrl.modelManager.showStatus(_("validating links"))
        modelLinks = set()
        self.remoteResourceLocElements = set()
        self.genericArcArcroles = set()
        for baseSetExtLinks in modelXbrl.baseSets.values():
            for baseSetExtLink in baseSetExtLinks:
                modelLinks.add(baseSetExtLink)    # ext links are unique (no dups)
        for modelLink in modelLinks:
            fromToArcs = {}
            locLabels = {}
            resourceLabels = {}
            resourceArcTos = []
            for arcElt in modelLink.iterchildren():
                if isinstance(arcElt,ModelObject):
                    xlinkType = arcElt.get("{http://www.w3.org/1999/xlink}type")
                    # locator must have an href
                    if xlinkType == "locator":
                        if arcElt.get("{http://www.w3.org/1999/xlink}href") is None:
                            modelXbrl.uuidError("08ac6fbeba7f4799938acacd8aaa4de8",
                                modelObject=arcElt,
                                linkrole=modelLink.role, 
                                xlinkLabel=arcElt.get("{http://www.w3.org/1999/xlink}label")) 
                        locLabels[arcElt.get("{http://www.w3.org/1999/xlink}label")] = arcElt
                    elif xlinkType == "resource":
                        resourceLabels[arcElt.get("{http://www.w3.org/1999/xlink}label")] = arcElt
                    # can be no duplicated arcs between same from and to
                    elif xlinkType == "arc":
                        fromLabel = arcElt.get("{http://www.w3.org/1999/xlink}from")
                        toLabel = arcElt.get("{http://www.w3.org/1999/xlink}to")
                        fromTo = (fromLabel,toLabel)
                        if fromTo in fromToArcs:
                            modelXbrl.uuidError("ef112b45410e47df99f0b2e9bb21ab85",
                                modelObject=arcElt,
                                linkrole=modelLink.role, 
                                xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
                        else:
                            fromToArcs[fromTo] = arcElt
                        if arcElt.namespaceURI == XbrlConst.link:
                            if arcElt.localName in arcNamesTo21Resource: #("labelArc","referenceArc"):
                                resourceArcTos.append((toLabel, arcElt.get("use"), arcElt))
                        elif self.isGenericArc(arcElt):
                            arcrole = arcElt.get("{http://www.w3.org/1999/xlink}arcrole")
                            self.genericArcArcroles.add(arcrole)
                            if arcrole in (XbrlConst.elementLabel, XbrlConst.elementReference):
                                resourceArcTos.append((toLabel, arcrole, arcElt))
                    # values of type (not needed for validating parsers)
                    if xlinkType not in xlinkTypeValues: # ("", "simple", "extended", "locator", "arc", "resource", "title", "none"):
                        modelXbrl.uuidError("aff57ed36e624bed8b40f94bd70e4ed1",
                            modelObject=arcElt, linkrole=modelLink.role, xlinkType=xlinkType)
                    # values of actuate (not needed for validating parsers)
                    xlinkActuate = arcElt.get("{http://www.w3.org/1999/xlink}actuate")
                    if xlinkActuate not in xlinkActuateValues: # ("", "onLoad", "onRequest", "other", "none"):
                        modelXbrl.uuidError("ae423c025a8a41649912331c0a6dc472",
                            modelObject=arcElt, linkrole=modelLink.role, xlinkActuate=xlinkActuate)
                    # values of show (not needed for validating parsers)
                    xlinkShow = arcElt.get("{http://www.w3.org/1999/xlink}show")
                    if xlinkShow not in xlinkShowValues: # ("", "new", "replace", "embed", "other", "none"):
                        modelXbrl.uuidError("e3ba9cc9eed54e29ae5ff17b2425b33b",
                            modelObject=arcElt, linkrole=modelLink.role, xlinkShow=xlinkShow)
            # check from, to of arcs have a resource or loc
            for fromTo, arcElt in fromToArcs.items():
                fromLabel, toLabel in fromTo
                for name, value, sect in (("from", fromLabel, "3.5.3.9.2"),("to",toLabel, "3.5.3.9.3")):
                    if value not in locLabels and value not in resourceLabels:
                        modelXbrl.error("xbrl.{0}:arcResource".format(sect),
                            _("Arc in extended link %(linkrole)s from %(xlinkLabelFrom)s to %(xlinkLabelTo)s attribute '%(attribute)s' has no matching loc or resource label"),
                            modelObject=arcElt, 
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel, 
                            attribute=name)
                if arcElt.localName == "footnoteArc" and arcElt.namespaceURI == XbrlConst.link and \
                   arcElt.get("{http://www.w3.org/1999/xlink}arcrole") == XbrlConst.factFootnote:
                    if fromLabel not in locLabels:
                        modelXbrl.uuidError("e7bdc978376c461fb0462913d8da47a5",
                            modelObject=arcElt, 
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
                    if toLabel not in resourceLabels or qname(resourceLabels[toLabel]) != XbrlConst.qnLinkFootnote:
                        modelXbrl.uuidError("f4cbfb88ffa64aaaaae54bca9ae1613e",
                            modelObject=arcElt, 
                            linkrole=modelLink.role, xlinkLabelFrom=fromLabel, xlinkLabelTo=toLabel)
            # check unprohibited label arcs to remote locs
            for resourceArcTo in resourceArcTos:
                resourceArcToLabel, resourceArcUse, arcElt = resourceArcTo
                if resourceArcToLabel in locLabels:
                    toLabel = locLabels[resourceArcToLabel]
                    if resourceArcUse == "prohibited":
                        self.remoteResourceLocElements.add(toLabel)
                    else:
                        modelXbrl.uuidError("f6ed821340a647bea797cbf999fb3409",
                            modelObject=arcElt, 
                            linkrole=modelLink.role, 
                            xlinkLabel=resourceArcToLabel,
                            xlinkHref=toLabel.get("{http://www.w3.org/1999/xlink}href"))
                elif resourceArcToLabel in resourceLabels:
                    toResource = resourceLabels[resourceArcToLabel]
                    if resourceArcUse == XbrlConst.elementLabel:
                        if not self.isGenericLabel(toResource):
                            modelXbrl.uuidError("85fcb48dec75412abc1b6a2f5552bd3b",
                                modelObject=arcElt, 
                                linkrole=modelLink.role, 
                                xlinkLabel=resourceArcToLabel)
                    elif resourceArcUse == XbrlConst.elementReference:
                        if not self.isGenericReference(toResource):
                            modelXbrl.uuidError("cb4d8c3b914f4ecd9e182e7758e6e0be",
                                modelObject=arcElt, 
                                linkrole=modelLink.role, 
                                xlinkLabel=resourceArcToLabel)
            resourceArcTos = None # dereference arcs

        modelXbrl.dimensionDefaultConcepts = {}
        modelXbrl.qnameDimensionDefaults = {}
        modelXbrl.qnameDimensionContextElement = {}
        # check base set cycles, dimensions
        modelXbrl.modelManager.showStatus(_("validating relationship sets"))
        for baseSetKey in modelXbrl.baseSets.keys():
            arcrole, ELR, linkqname, arcqname = baseSetKey
            if arcrole.startswith("XBRL-") or ELR is None or \
                linkqname is None or arcqname is None:
                continue
            elif arcrole in XbrlConst.standardArcroleCyclesAllowed:
                # TODO: table should be in this module, where it is used
                cyclesAllowed, specSect = XbrlConst.standardArcroleCyclesAllowed[arcrole]
            elif arcrole in self.modelXbrl.arcroleTypes and len(self.modelXbrl.arcroleTypes[arcrole]) > 0:
                cyclesAllowed = self.modelXbrl.arcroleTypes[arcrole][0].cyclesAllowed
                if arcrole in self.genericArcArcroles:
                    specSect = "xbrlgene:violatedCyclesConstraint"
                else:
                    specSect = "xbrl.5.1.4.3:cycles"
            else:
                cyclesAllowed = "any"
                specSect = None
            if cyclesAllowed != "any" or arcrole in (XbrlConst.summationItem,) \
                                      or arcrole in self.genericArcArcroles  \
                                      or arcrole.startswith(XbrlConst.formulaStartsWith):
                relsSet = modelXbrl.relationshipSet(arcrole,ELR,linkqname,arcqname)
            if cyclesAllowed != "any" and \
                   (XbrlConst.isStandardExtLinkQname(linkqname) and XbrlConst.isStandardArcQname(arcqname)) \
                   or arcrole in self.genericArcArcroles:
                noUndirected = cyclesAllowed == "none"
                fromRelationships = relsSet.fromModelObjects()
                for relFrom, rels in fromRelationships.items():
                    cycleFound = self.fwdCycle(relsSet, rels, noUndirected, {relFrom})
                    if cycleFound is not None:
                        path = str(relFrom.qname) + " " + " - ".join(
                            "{0}:{1} {2}".format(rel.modelDocument.basename, rel.sourceline, rel.toModelObject.qname)
                            for rel in reversed(cycleFound[1:]))
                        modelXbrl.error(specSect,
                            _("Relationships have a %(cycle)s cycle in arcrole %(arcrole)s \nlink role %(linkrole)s \nlink %(linkname)s, \narc %(arcname)s, \npath %(path)s"),
                            modelObject=cycleFound[1], cycle=cycleFound[0], path=path,
                            arcrole=arcrole, linkrole=ELR, linkname=linkqname, arcname=arcqname), 
                        break
                
            # check calculation arcs for weight issues (note calc arc is an "any" cycles)
            if arcrole == XbrlConst.summationItem:
                for modelRel in relsSet.modelRelationships:
                    weight = modelRel.weight
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if weight == 0:
                            modelXbrl.uuidError("77f7011c9d994e9b8f8d5736084ccb11",
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR), 
                        fromBalance = fromConcept.balance
                        toBalance = toConcept.balance
                        if fromBalance and toBalance:
                            if (fromBalance == toBalance and weight < 0) or \
                               (fromBalance != toBalance and weight > 0):
                                modelXbrl.uuidError("749f7375a53e4d48bd0822a04d53822e",
                                    modelObject=modelRel, weight=weight,
                                    source=fromConcept.qname, target=toConcept.qname, linkrole=ELR, 
                                    sourceBalance=fromBalance, targetBalance=toBalance)
                        if not fromConcept.isNumeric or not toConcept.isNumeric:
                            modelXbrl.uuidError("c422b796b2e44a83be3bbaca001e50c0",
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR, 
                                sourceNumericDecorator="" if fromConcept.isNumeric else _(" (non-numeric)"), 
                                targetNumericDecorator="" if toConcept.isNumeric else _(" (non-numeric)"))
            # check presentation relationships for preferredLabel issues
            elif arcrole == XbrlConst.parentChild:
                for modelRel in relsSet.modelRelationships:
                    preferredLabel = modelRel.preferredLabel
                    toConcept = modelRel.toModelObject
                    if preferredLabel is not None and toConcept is not None and \
                       toConcept.label(preferredLabel=preferredLabel,fallbackToQname=False) is None:
                        modelXbrl.uuidError("424b12e125df4c27961430ce793d8f5b",
                            modelObject=modelRel,
                            source=modelRel.fromModelObject.qname, target=toConcept.qname, linkrole=ELR, 
                            preferredLabel=preferredLabel)
            # check essence-alias relationships
            elif arcrole == XbrlConst.essenceAlias:
                for modelRel in relsSet.modelRelationships:
                    fromConcept = modelRel.fromModelObject
                    toConcept = modelRel.toModelObject
                    if fromConcept is not None and toConcept is not None:
                        if fromConcept.type != toConcept.type or fromConcept.periodType != toConcept.periodType:
                            modelXbrl.uuidError("4616cfbd653045ee990ba03e70c67016",
                                modelObject=modelRel,
                                source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
                        fromBalance = fromConcept.balance
                        toBalance = toConcept.balance
                        if fromBalance and toBalance:
                            if fromBalance and toBalance and fromBalance != toBalance:
                                modelXbrl.uuidError("52f10575987f4dcc959916311772ea17",
                                    modelObject=modelRel,
                                    source=fromConcept.qname, target=toConcept.qname, linkrole=ELR)
            elif modelXbrl.hasXDT and arcrole.startswith(XbrlConst.dimStartsWith):
                ValidateXbrlDimensions.checkBaseSet(self, arcrole, ELR, relsSet)             
            elif modelXbrl.hasFormulae and arcrole.startswith(XbrlConst.formulaStartsWith):
                ValidateFormula.checkBaseSet(self, arcrole, ELR, relsSet)
        modelXbrl.isDimensionsValidated = True
                            
        # instance checks
        modelXbrl.modelManager.showStatus(_("validating instance"))
        self.footnoteRefs = set()
        if modelXbrl.modelDocument.type == ModelDocument.Type.INSTANCE or \
           modelXbrl.modelDocument.type == ModelDocument.Type.INLINEXBRL:
            for f in modelXbrl.facts:
                concept = f.concept
                if concept is not None:
                    if concept.isNumeric:
                        unit = f.unit
                        if f.unitID is None or unit is None:
                            self.modelXbrl.uuidError("9b82e52350da410db846766a3d9ef416",
                                 modelObject=f, fact=f.qname, contextID=f.contextID)
                        else:
                            if concept.isMonetary:
                                measures = unit.measures
                                if not measures or len(measures[0]) != 1 or len(measures[1]) != 0 or \
                                    measures[0][0].namespaceURI != XbrlConst.iso4217 or \
                                    not self.isoCurrencyPattern.match(measures[0][0].localName):
                                        self.modelXbrl.uuidError("347d0a8c7f5341aeb4113dff0ddc01cb",
                                             modelObject=f, fact=f.qname, contextID=f.contextID, unitID=f.unitID)
                            elif concept.isShares:
                                measures = unit.measures
                                if not measures or len(measures[0]) != 1 or len(measures[1]) != 0 or \
                                    measures[0][0] != XbrlConst.qnXbrliShares:
                                        self.modelXbrl.uuidError("3d22804a534641e28db39f6838dd7b31",
                                            modelObject=f, fact=f.qname, contextID=f.contextID, unitID=f.unitID)
                    precision = f.precision
                    hasPrecision = precision is not None
                    if hasPrecision and precision != "INF" and not precision.isdigit():
                        self.modelXbrl.uuidError("ca8cef4c4eb8439283051077eb92cc82",
                            modelObject=f, fact=f.qname, contextID=f.contextID, precision=precision)
                    decimals = f.decimals
                    hasDecimals = decimals is not None
                    if hasPrecision and not self.precisionPattern.match(precision):
                        self.modelXbrl.uuidError("ca8cef4c4eb8439283051077eb92cc82",
                            modelObject=f, fact=f.qname, contextID=f.contextID, precision=precision)
                    if hasPrecision and hasDecimals:
                        self.modelXbrl.uuidError("62c67745d2214255809e0dce0baacc60",
                            modelObject=f, fact=f.qname, contextID=f.contextID)
                    if hasDecimals and not self.decimalsPattern.match(decimals):
                        self.modelXbrl.uuidError("557d1ec7b31c4037940177088e24b90b",
                            modelObject=f, fact=f.qname, contextID=f.contextID, decimals=decimals)
                    if concept.isItem:
                        context = f.context
                        if context is None:
                            self.modelXbrl.uuidError("021f4f5991d64fc6b771bec4ad3d9065",
                                modelObject=f, fact=f.qname)
                        else:
                            periodType = concept.periodType
                            if (periodType == "instant" and not context.isInstantPeriod) or \
                               (periodType == "duration" and not (context.isStartEndPeriod or context.isForeverPeriod)):
                                self.modelXbrl.uuidError("7eee24bae2d4405c8b182f71e449a30a",
                                    modelObject=f, fact=f.qname, contextID=f.contextID, periodType=periodType)
                            if modelXbrl.hasXDT:
                                ValidateXbrlDimensions.checkFact(self, f)
                        # check precision and decimals
                        if f.xsiNil == "true":
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.uuidError("1762a325b74e43a5b15e422cbcabd430",
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                        elif concept.isFraction:
                            if hasPrecision or hasDecimals:
                                self.modelXbrl.uuidError("69637e4b01244002b9f461e328a578e7",
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                                numerator, denominator = f.fractionValue
                                if not (numerator == "INF" or numerator.isnumeric()):
                                    self.modelXbrl.uuidError("24d47c6c33a443ddb10e831197ccd08f",
                                        modelObject=f, fact=f.qname, contextID=f.contextID, numerator=numerator)
                                if not denominator.isnumeric() or int(denominator) == 0:
                                    self.modelXbrl.uuidError("51ca8038f2fb4202afe68cecc468d28c",
                                        modelObject=f, fact=f.qname, contextID=f.contextID, denominator=denominator)
                        else:
                            if modelXbrl.modelDocument.type != ModelDocument.Type.INLINEXBRL:
                                for child in f.iterchildren():
                                    if isinstance(child,ModelObject):
                                        self.modelXbrl.uuidError("88eadbca7529464eadb47dd5941dd1f0",
                                            modelObject=f, fact=f.qname, contextID=f.contextID, childElementName=child.prefixedName)
                                        break
                            if concept.isNumeric and not hasPrecision and not hasDecimals:
                                self.modelXbrl.uuidError("7bb18d6779794e0a8cf2d987c08905f4",
                                    modelObject=f, fact=f.qname, contextID=f.contextID)
                    elif concept.isTuple:
                        if f.contextID:
                            self.modelXbrl.uuidError("32d89ddbd61948be8db32391d0db4163",
                                modelObject=f, fact=f.qname)
                        if hasPrecision or hasDecimals:
                            self.modelXbrl.uuidError("78d4ad51ee7942e38e7c38027ef3eefa",
                                modelObject=f, fact=f.qname)
                        # custom attributes may be allowed by anyAttribute but not by 2.1
                        for attrQname, attrValue in XbrlUtil.attributes(self.modelXbrl, f):
                            if attrQname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
                                self.modelXbrl.uuidError("c7b4129370f84a379d304525e282ab21",
                                    modelObject=f, fact=f.qname, attribute=attrQname), 
                    else:
                        self.modelXbrl.uuidError("71f31abfa19e4bb5b8cf5150cf2fae02",
                            modelObject=f, fact=f.qname)
                        
                if isinstance(f, ModelInlineFact):
                    self.footnoteRefs.update(f.footnoteRefs)
            
            #instance checks
            for cntx in modelXbrl.contexts.values():
                if cntx.isStartEndPeriod:
                    try:
                        if cntx.endDatetime <= cntx.startDatetime:
                            self.modelXbrl.uuidError("4fd5801ab4df41108b838ca9bac761d1",
                                modelObject=cntx, contextID=cntx.id)
                    except (TypeError, ValueError) as err:
                        self.modelXbrl.uuidError("4735c58c19a246fa98c52ccbefa60ae6",
                            modelObject=cntx, contextID=cntx.id, error=err)
                elif cntx.isInstantPeriod:
                    try:
                        cntx.instantDatetime #parse field
                    except ValueError as err:
                        self.modelXbrl.uuidError("bef1bd7070804ef2a7e4ebd4683d3d96",
                            modelObject=cntx, contextID=cntx.id, error=err)
                self.segmentScenario(cntx.segment, cntx.id, "segment", "4.7.3.2")
                self.segmentScenario(cntx.scenario, cntx.id, "scenario", "4.7.4")
                if modelXbrl.hasXDT:
                    ValidateXbrlDimensions.checkContext(self,cntx)
                
            for unit in modelXbrl.units.values():
                mulDivMeasures = unit.measures
                if mulDivMeasures:
                    for measures in mulDivMeasures:
                        for measure in measures:
                            if measure.namespaceURI == XbrlConst.xbrli and not \
                                measure in (XbrlConst.qnXbrliPure, XbrlConst.qnXbrliShares):
                                    self.modelXbrl.uuidError("e263dd1d83074a58b3a010cb6bb88636",
                                        modelObject=unit, unitID=unit.id, measure=measure)
                    for numeratorMeasure in mulDivMeasures[0]:
                        if numeratorMeasure in mulDivMeasures[1]:
                            self.modelXbrl.uuidError("8c0c6b89e0554573b7d204210a482bc1",
                                modelObject=unit, unitID=unit.id, measure=numeratorMeasure)
                    
        #concepts checks
        modelXbrl.modelManager.showStatus(_("validating concepts"))
        for concept in modelXbrl.qnameConcepts.values():
            conceptType = concept.type
            if XbrlConst.isStandardNamespace(concept.qname.namespaceURI) or \
               not concept.modelDocument.inDTS:
                continue
            
            if concept.isTuple:
                # must be global
                if not concept.getparent().localName == "schema":
                    self.modelXbrl.uuidError("f20b36b592b34945a8ba1470a376ea30",
                        modelObject=concept, concept=concept.qname)
                if concept.periodType:
                    self.modelXbrl.uuidError("e847e212880e4ccfb52dc4233ae5c5c8",
                        modelObject=concept, concept=concept.qname)
                if concept.balance:
                    self.modelXbrl.uuidError("751c51ae278d42ed98e1ff133efc0c7a",
                        modelObject=concept, concept=concept.qname)
                if conceptType is not None:
                    # check attribute declarations
                    for attribute in conceptType.attributes.values():
                        if attribute.qname.namespaceURI in (XbrlConst.xbrli, XbrlConst.link, XbrlConst.xlink, XbrlConst.xl):
                            self.modelXbrl.uuidError("8f88a06efc3d414fb4ffe9ecdea87e32",
                                modelObject=concept, concept=concept.qname, attribute=attribute.qname)
                    # check for mixed="true" or simple content
                    if XmlUtil.descendantAttr(conceptType, XbrlConst.xsd, ("complexType", "complexContent"), "mixed") == "true":
                        self.modelXbrl.uuidError("59f895f4a2e94aa18031c62a9efdd8dd",
                            modelObject=concept, concept=concept.qname)
                    if XmlUtil.descendant(conceptType, XbrlConst.xsd, "simpleContent"):
                        self.modelXbrl.uuidError("670257e4a7374232a6443487dd3b77f2",
                            modelObject=concept, concept=concept.qname)
                    # child elements must be item or tuple
                    for elementQname in conceptType.elements:
                        childConcept = self.modelXbrl.qnameConcepts.get(elementQname)
                        if childConcept is None:
                            self.modelXbrl.uuidError("ce60741649a04b19a5d1f7c658cee012",
                                modelObject=concept, concept=str(concept.qname), tupleElement=elementQname)
                        elif not (childConcept.isItem or childConcept.isTuple or # isItem/isTuple do not include item or tuple itself
                                  childConcept.qname == XbrlConst.qnXbrliItem or # subs group includes item as member
                                  childConcept.qname == XbrlConst.qnXbrliTuple):
                            self.modelXbrl.uuidError("540841271c24495f911cda49b88e801f",
                                modelObject=concept, concept=concept.qname, tupleElement=elementQname)
            elif concept.isItem:
                if concept.periodType not in periodTypeValues: #("instant","duration"):
                    self.modelXbrl.uuidError("d78669307dc84b6c86c47c6929acb394",
                        modelObject=concept, concept=concept.qname)
                if concept.isMonetary:
                    if concept.balance not in balanceValues: #(None, "credit","debit"):
                        self.modelXbrl.uuidError("ea5f7973010a4104a6d1e5f2d8c42fb5",
                            modelObject=concept, concept=concept.qname, balance=concept.balance)
                else:
                    if concept.balance:
                        self.modelXbrl.uuidError("a37e4eae4f0f4a4fa9d742f046b4c003",
                            modelObject=concept, concept=concept.qname)
                if concept.baseXbrliType not in baseXbrliTypes:
                    self.modelXbrl.uuidError("c60c970bb20244969794287173b81622",
                        modelObject=concept, concept=concept.qname, itemType=concept.baseXbrliType)
                if modelXbrl.hasXDT:
                    if concept.isHypercubeItem and not concept.abstract == "true":
                        self.modelXbrl.uuidError("bfdabf7d5dbd48a484de796831d081bc",
                            modelObject=concept, concept=concept.qname)
                    elif concept.isDimensionItem and not concept.abstract == "true":
                        self.modelXbrl.uuidError("a49b1a3209484fccac5122e7db48b07f",
                            modelObject=concept, concept=concept.qname)
            if modelXbrl.hasXDT:
                ValidateXbrlDimensions.checkConcept(self, concept)
            
        modelXbrl.modelManager.showStatus(_("validating DTS"))
        self.DTSreferenceResourceIDs = {}
        ValidateXbrlDTS.checkDTS(self, modelXbrl.modelDocument, [])
        del self.DTSreferenceResourceIDs
        
        if self.validateCalcLB:
            modelXbrl.modelManager.showStatus(_("Validating instance calculations"))
            ValidateXbrlCalcs.validate(modelXbrl, inferPrecision=(not self.validateInferDecimals))
            
        if (modelXbrl.modelManager.validateUtr or
            (self.parameters and self.parameters.get(qname("forceUtrValidation",noPrefixIsNoNamespace=True),(None,"false"))[1] == "true") or
             #(self.validateEFM and 
             #any((concept.namespaceURI in self.disclosureSystem.standardTaxonomiesDict) 
             #    for concept in self.modelXbrl.nameConcepts.get("UTR",())))):
            (self.validateEFM and any(modelDoc.definesUTR for modelDoc in self.modelXbrl.urlDocs.values()))):
            ValidateUtr.validate(modelXbrl)
            
        if modelXbrl.hasFormulae:
            ValidateFormula.validate(self)
            
        modelXbrl.modelManager.showStatus(_("ready"), 2000)
        
    def fwdCycle(self, relsSet, rels, noUndirected, fromConcepts, cycleType="directed", revCycleRel=None):
        for rel in rels:
            if revCycleRel is not None and rel.isIdenticalTo(revCycleRel):
                continue # don't double back on self in undirected testing
            relTo = rel.toModelObject
            if relTo in fromConcepts: #forms a directed cycle
                return [cycleType,rel]
            fromConcepts.add(relTo)
            nextRels = relsSet.fromModelObject(relTo)
            foundCycle = self.fwdCycle(relsSet, nextRels, noUndirected, fromConcepts)
            if foundCycle is not None:
                foundCycle.append(rel)
                return foundCycle
            fromConcepts.discard(relTo)
            # look for back path in any of the ELRs visited (pass None as ELR)
            if noUndirected:
                foundCycle = self.revCycle(relsSet, relTo, rel, fromConcepts)
                if foundCycle is not None:
                    foundCycle.append(rel)
                    return foundCycle
        return None
    
    def revCycle(self, relsSet, toConcept, turnbackRel, fromConcepts):
        for rel in relsSet.toModelObject(toConcept):
            if not rel.isIdenticalTo(turnbackRel):
                relFrom = rel.fromModelObject
                if relFrom in fromConcepts:
                    return ["undirected",rel]
                fromConcepts.add(relFrom)
                foundCycle = self.revCycle(relsSet, relFrom, turnbackRel, fromConcepts)
                if foundCycle is not None:
                    foundCycle.append(rel)
                    return foundCycle
                fwdRels = relsSet.fromModelObject(relFrom)
                foundCycle = self.fwdCycle(relsSet, fwdRels, True, fromConcepts, cycleType="undirected", revCycleRel=rel)
                if foundCycle is not None:
                    foundCycle.append(rel)
                    return foundCycle
                fromConcepts.discard(relFrom)
        return None
    
    def segmentScenario(self, element, contextId, name, sect, topLevel=True):
        if topLevel:
            if element is None:
                return  # nothing to check
        else:
            if element.namespaceURI == XbrlConst.xbrli:
                self.modelXbrl.error("xbrl.{0}:{1}XbrliElement".format(sect,name),
                    _("Context %(contextID)s %(contextElement)s cannot have xbrli element %(elementName)s"),
                    modelObject=element, contextID=contextId, contextElement=name, elementName=element.prefixedName)
            else:
                concept = self.modelXbrl.qnameConcepts.get(qname(element))
                if concept is not None and (concept.isItem or concept.isTuple):
                    self.modelXbrl.error("xbrl.{0}:{1}ItemOrTuple".format(sect,name),
                        _("Context %(contextID)s %(contextElement)s cannot have item or tuple element %(elementName)s"),
                        modelObject=element, contextID=contextId, contextElement=name, elementName=element.prefixedName)
        hasChild = False
        for child in element.iterchildren():
            if isinstance(child,ModelObject):
                self.segmentScenario(child, contextId, name, sect, topLevel=False)
                hasChild = True
        if topLevel and not hasChild:
            self.modelXbrl.error("xbrl.{0}:{1}Empty".format(sect,name),
                _("Context %(contextID)s %(contextElement)s cannot be empty"),
                modelObject=element, contextID=contextId, contextElement=name)
        
    def isGenericObject(self, elt, genQname):
        return self.modelXbrl.isInSubstitutionGroup(qname(elt),genQname)
    
    def isGenericLink(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenLink)
    
    def isGenericArc(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenArc)
    
    def isGenericResource(self, elt):
        return self.isGenericObject(elt.getparent(), XbrlConst.qnGenLink)

    def isGenericLabel(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenLabel)

    def isGenericReference(self, elt):
        return self.isGenericObject(elt, XbrlConst.qnGenReference)

    def executeCallTest(self, modelXbrl, name, callTuple, testTuple):
        self.modelXbrl = modelXbrl
        ValidateFormula.executeCallTest(self, name, callTuple, testTuple)
                
