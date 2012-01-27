'''
Created on Oct 17, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
from arelle import (ModelDocument, ModelDtsObject, HtmlUtil, UrlUtil, XmlUtil, XbrlUtil, XbrlConst,
                    XmlValidate)
from arelle.ModelObject import ModelObject, ModelComment
from arelle.ModelValue import qname
from lxml import etree

instanceSequence = {"schemaRef":1, "linkbaseRef":2, "roleRef":3, "arcroleRef":4}
schemaTop = {"import", "include", "redefine"}
schemaBottom = {"element", "attribute", "notation", "simpleType", "complexType", "group", "attributeGroup"}
xsd1_1datatypes = {qname(XbrlConst.xsd,'anyAtomicType'), qname(XbrlConst.xsd,'yearMonthDuration'), qname(XbrlConst.xsd,'dayTimeDuration'), qname(XbrlConst.xsd,'dateTimeStamp'), qname(XbrlConst.xsd,'precisionDecimal')}

def checkDTS(val, modelDocument, visited):
    visited.append(modelDocument)
    for referencedDocument in modelDocument.referencesDocument.keys():
        if referencedDocument not in visited:
            checkDTS(val, referencedDocument, visited)
            
    # skip processing versioning report here
    if modelDocument.type == ModelDocument.Type.VERSIONINGREPORT:
        return
    
    # skip system schemas
    if modelDocument.type == ModelDocument.Type.SCHEMA:
        if XbrlConst.isStandardNamespace(modelDocument.targetNamespace):
            return
        val.hasLinkRole = val.hasLinkPart = val.hasContextFragment = val.hasAbstractItem = \
            val.hasTuple = val.hasNonAbstractElement = val.hasType = val.hasEnumeration = \
            val.hasDimension = val.hasDomain = val.hasHypercube = False

    
    # check for linked up hrefs
    isInstance = (modelDocument.type == ModelDocument.Type.INSTANCE or
                  modelDocument.type == ModelDocument.Type.INLINEXBRL)
    
    for hrefElt, hrefedDoc, hrefId in modelDocument.hrefObjects:
        hrefedObj = None
        hrefedElt = None
        if hrefedDoc is None:
            val.modelXbrl.uuidError("76b323275d4645abba40f112bb291e5a",
                modelObject=hrefElt, 
                elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
        elif hrefId:
            if hrefId in hrefedDoc.idObjects:
                hrefedObj = hrefedDoc.idObjects[hrefId]
                hrefedElt = hrefedObj
            else:
                hrefedElt = XmlUtil.xpointerElement(hrefedDoc,hrefId)
                if hrefedElt is None:
                    val.modelXbrl.uuidError("7c0054bddb4049d9ba4300b215176fe4",
                        modelObject=hrefElt, 
                        elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                else:
                    # find hrefObj
                    for docModelObject in hrefedDoc.modelObjects:
                        if docModelObject == hrefedElt:
                            hrefedObj = docModelObject
                            break
        else:
            hrefedElt = hrefedDoc.xmlRootElement
            hrefedObj = hrefedDoc
            
        if hrefId:  #check scheme regardless of whether document loaded 
            # check all xpointer schemes
            for scheme, path in XmlUtil.xpointerSchemes(hrefId):
                if scheme != "element":
                    val.modelXbrl.uuidError("3f932ee0ee1b4edbbf105150a5af3d89",
                        modelObject=hrefElt, 
                        elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"),
                        scheme=scheme)
                    break
                elif val.validateDisclosureSystem:
                    val.modelXbrl.uuidError("0a18bb773853433d8df5e409ed1f8550",
                        modelObject=hrefElt, 
                        elementHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
        # check href'ed target if a linkbaseRef
        if hrefElt.namespaceURI == XbrlConst.link and hrefedElt is not None:
            if hrefElt.localName == "linkbaseRef":
                # check linkbaseRef target
                if hrefedElt.namespaceURI != XbrlConst.link or hrefedElt.localName != "linkbase":
                    val.modelXbrl.uuidError("a890c69dbd6f4efda8199e89398eb2f9",
                        modelObject=hrefElt, 
                        linkbaseHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                if hrefElt.get("{http://www.w3.org/1999/xlink}role") is not None:
                    role = hrefElt.get("{http://www.w3.org/1999/xlink}role")
                    for linkNode in hrefedElt.iterchildren():
                        if (isinstance(linkNode,ModelObject) and
                            linkNode.get("{http://www.w3.org/1999/xlink}type") == "extended"):
                            ln = linkNode.localName
                            ns = linkNode.namespaceURI
                            if (role == "http://www.xbrl.org/2003/role/calculationLinkbaseRef" and \
                                (ns != XbrlConst.link or ln != "calculationLink")) or \
                               (role == "http://www.xbrl.org/2003/role/definitionLinkbaseRef" and \
                                (ns != XbrlConst.link or ln != "definitionLink")) or \
                               (role == "http://www.xbrl.org/2003/role/presentationLinkbaseRef" and \
                                (ns != XbrlConst.link or ln != "presentationLink")) or \
                               (role == "http://www.xbrl.org/2003/role/labelLinkbaseRef" and \
                                (ns != XbrlConst.link or ln != "labelLink")) or \
                               (role == "http://www.xbrl.org/2003/role/referenceLinkbaseRef" and \
                                (ns != XbrlConst.link or ln != "referenceLink")):
                                val.modelXbrl.uuidError("fe77628a843146ad89a9c6ed60aa4f63",
                                    modelObject=hrefElt, 
                                    linkbaseHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"),
                                    role=role, link=linkNode.prefixedName)
            elif hrefElt.localName == "schemaRef":
                # check schemaRef target
                if hrefedElt.namespaceURI != XbrlConst.xsd or hrefedElt.localName != "schema":
                    val.modelXbrl.uuidError("b9b34b33518c4470b06c853063f21a06",
                        modelObject=hrefElt, schemaRef=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
            # check loc target 
            elif hrefElt.localName == "loc":
                linkElt = hrefElt.getparent()
                if linkElt.namespaceURI ==  XbrlConst.link:
                    acceptableTarget = False
                    hrefEltKey = linkElt.localName
                    if hrefElt in val.remoteResourceLocElements:
                        hrefEltKey += "ToResource"
                    for tgtTag in {
                               "labelLink":("{http://www.w3.org/2001/XMLSchema}element", "{http://www.xbrl.org/2003/linkbase}label"),
                               "labelLinkToResource":("{http://www.xbrl.org/2003/linkbase}label",),
                               "referenceLink":("{http://www.w3.org/2001/XMLSchema}element", "{http://www.xbrl.org/2003/linkbase}reference"),
                               "referenceLinkToResource":("{http://www.xbrl.org/2003/linkbase}reference",),
                               "calculationLink":("{http://www.w3.org/2001/XMLSchema}element",),
                               "definitionLink":("{http://www.w3.org/2001/XMLSchema}element",),
                               "presentationLink":("{http://www.w3.org/2001/XMLSchema}element",),
                               "footnoteLink":("XBRL-item-or-tuple",) }[hrefEltKey]:
                        if tgtTag == "XBRL-item-or-tuple":
                            concept = val.modelXbrl.qnameConcepts.get(qname(hrefedElt))
                            acceptableTarget =  isinstance(concept, ModelDtsObject.ModelConcept) and \
                                                (concept.isItem or concept.isTuple)
                        elif hrefedElt.tag == tgtTag:
                            acceptableTarget = True
                    if not acceptableTarget:
                        val.modelXbrl.error("xbrl.{0}:{1}LocTarget".format(
                                        {"labelLink":"5.2.5.1",
                                         "referenceLink":"5.2.3.1",
                                         "calculationLink":"5.2.5.1",
                                         "definitionLink":"5.2.6.1",
                                         "presentationLink":"5.2.4.1",
                                         "footnoteLink":"4.11.1.1"}[linkElt.localName],
                                         linkElt.localName),
                             _("%(linkElement)s loc href %(locHref)s must identify a concept or label"),
                             modelObject=hrefElt, linkElement=linkElt.localName,
                             locHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                    if isInstance and not XmlUtil.isDescendantOf(hrefedElt, modelDocument.xmlRootElement):
                        val.modelXbrl.uuidError("e22c27407b144a6d92bf9374870345f9",
                             modelObject=hrefElt, locHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))
                # non-standard link holds standard loc, href must be discovered document 
                if not hrefedDoc.inDTS:
                    val.modelXbrl.uuidError("539034933ba14eb48a838149eb75ca17",
                        modelObject=hrefElt, locHref=hrefElt.get("{http://www.w3.org/1999/xlink}href"))

    # used in linkbase children navigation but may be errant linkbase elements                            
    val.roleRefURIs = {}
    val.arcroleRefURIs = {}
    val.elementIDs = set()
    val.annotationsCount = 0  
            
    # XML validation checks (remove if using validating XML)
    val.extendedElementName = None
    if (modelDocument.uri.startswith(val.modelXbrl.uriDir) and
        modelDocument.targetNamespace not in val.disclosureSystem.baseTaxonomyNamespaces and 
        modelDocument.xmlDocument):
        val.valUsedPrefixes = set()
        val.schemaRoleTypes = {}
        val.schemaArcroleTypes = {}
        val.referencedNamespaces = set()

        val.containsRelationship = False
        
        checkElements(val, modelDocument, modelDocument.xmlDocument)
        
        if (modelDocument.type == ModelDocument.Type.INLINEXBRL and 
            val.validateGFM and
            (val.documentTypeEncoding.lower() != 'utf-8' or val.metaContentTypeEncoding.lower() != 'utf-8')):
            val.modelXbrl.uuidError("c73907a8e1b843628e597384e5781198",
                    modelXbrl=modelDocument, encoding=val.documentTypeEncoding, 
                    metaContentTypeEncoding=val.metaContentTypeEncoding)
        if val.validateSBRNL:
            if modelDocument.type in (ModelDocument.Type.SCHEMA, ModelDocument.Type.LINKBASE):
                isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
                docinfo = modelDocument.xmlDocument.docinfo
                if docinfo and docinfo.xml_version != "1.0":
                    val.modelXbrl.uuidError("161b2e9e98ca4a11b9c48f06270e7dfb" if isSchema else "d3260aa0480d449d9baec71179e1a7f7",
                            modelObject=modelDocument, docType=modelDocument.gettype().title(), 
                            xmlVersion=docinfo.xml_version)
                if modelDocument.documentEncoding.lower() != "utf-8":
                    val.modelXbrl.uuidError("cbef121ecc5f47c9842d95ec49dfd393" if isSchema else "bd3f1521026c470fb23a5d67eaeb327a",
                            modelObject=modelDocument, docType=modelDocument.gettype().title(), 
                            xmlEncoding=modelDocument.documentEncoding)
                lookingForPrecedingComment = True
                for commentNode in modelDocument.xmlRootElement.itersiblings(preceding=True):
                    if isinstance(commentNode,etree._Comment):
                        if lookingForPrecedingComment:
                            lookingForPrecedingComment = False
                        else:
                            val.modelXbrl.uuidError("38d466bb38ad4b4791362ed65196a0b4" if isSchema else "c05271474cbb426c91c7a7df3710dbea",
                                    modelObject=modelDocument, docType=modelDocument.gettype().title())
                if lookingForPrecedingComment:
                    val.modelXbrl.uuidError("80e018a4c3e14d829ebda1974d7297fe" if isSchema else "c9387255e0ec4f519660d0bcc4b1dd71",
                        modelObject=modelDocument, docType=modelDocument.gettype().title())
                
                # check namespaces are used
                for prefix, ns in modelDocument.xmlRootElement.nsmap.items():
                    if ((prefix not in val.valUsedPrefixes) and
                        (modelDocument.type != ModelDocument.Type.SCHEMA or ns != modelDocument.targetNamespace)):
                        val.modelXbrl.uuidError("f88b15bd384e4ccd806e7408f4a053e5" if modelDocument.type == ModelDocument.Type.SCHEMA else "7f7fedac8f3f4170b51bd0f8b3c1d8fe",
                            modelObject=modelDocument, docType=modelDocument.gettype().title(), 
                            declaration=("xmlns" + (":" + prefix if prefix else "") + "=" + ns))
                        
                if isSchema and val.annotationsCount > 1:
                    val.modelXbrl.uuidError("54b416f60a804dbc9c1a3460f93dd088",
                        modelObject=modelDocument, annotationsCount=val.annotationsCount)
            if modelDocument.type ==  ModelDocument.Type.LINKBASE:
                if not val.containsRelationship:
                    val.modelXbrl.uuidError("9746fa5e2a484d93ad942290fa94a83c",
                        modelObject=modelDocument)
            else: # SCHEMA
                # check for unused imports
                for referencedDocument in modelDocument.referencesDocument.keys():
                    if (referencedDocument.type == ModelDocument.Type.SCHEMA and
                        referencedDocument.targetNamespace not in {XbrlConst.xbrli, XbrlConst.link} and
                        referencedDocument.targetNamespace not in val.referencedNamespaces):
                        val.modelXbrl.uuidError("fd8ced187b5f4cf28ce3d13ba1e45c53",
                            modelObject=modelDocument, importedFile=referencedDocument.basename)
        del val.valUsedPrefixes
        del val.schemaRoleTypes
        del val.schemaArcroleTypes

    val.roleRefURIs = None
    val.arcroleRefURIs = None
    val.elementIDs = None

def checkElements(val, modelDocument, parent):
    isSchema = modelDocument.type == ModelDocument.Type.SCHEMA
    if isinstance(parent, ModelObject):
        parentXlinkType = parent.get("{http://www.w3.org/1999/xlink}type")
        isInstance = parent.namespaceURI == XbrlConst.xbrli and parent.localName == "xbrl"
        parentIsLinkbase = parent.namespaceURI == XbrlConst.link and parent.localName == "linkbase"
        parentIsSchema = parent.namespaceURI == XbrlConst.xsd and parent.localName == "schema"
        if isInstance or parentIsLinkbase:
            val.roleRefURIs = {}
            val.arcroleRefURIs = {}
        childrenIter = parent.iterchildren()
    else: # parent is document node, not an element
        parentXlinkType = None
        isInstance = False
        parentIsLinkbase = False
        childrenIter = (parent.getroot(),)
        if isSchema:
            val.inSchemaTop = True

    parentIsAppinfo = False
    if modelDocument.type == ModelDocument.Type.INLINEXBRL:
        if isinstance(parent,ModelObject): # element
            if parent.localName == "meta" and parent.namespaceURI == XbrlConst.xhtml and \
            parent.get("http-equiv").lower() == "content-type":
                val.metaContentTypeEncoding = HtmlUtil.attrValue(parent.get("content"), "charset")
        elif isinstance(parent,etree._ElementTree): # documentNode
            val.documentTypeEncoding = modelDocument.documentEncoding # parent.docinfo.encoding
            val.metaContentTypeEncoding = ""

    instanceOrder = 0
    if modelDocument.type == ModelDocument.Type.SCHEMA:
        ncnameTests = (("id","xbrl:xmlElementId"), 
                       ("name","xbrl.5.1.1:conceptName"))
    else:
        ncnameTests = (("id","xbrl:xmlElementId"),)
    for elt in childrenIter:
        if isinstance(elt,ModelObject):
            for name, errCode in ncnameTests:
                if elt.get(name) is not None:
                    attrValue = elt.get(name)
                    ''' done in XmlValidate now
                    if not val.NCnamePattern.match(attrValue):
                        val.modelXbrl.error(errCode,
                            _("Element %(element)s attribute %(attribute)s '%(value)s' is not an NCname"),
                            modelObject=elt, element=elt.prefixedName, attribute=name, value=attrValue)
                    '''
                    if name == "id" and attrValue in val.elementIDs:
                        val.modelXbrl.uuidError("92d865ee5b8f4318ae56414d7acc05e2",
                            modelObject=elt, element=elt.prefixedName, attribute=name, value=attrValue)
                    val.elementIDs.add(attrValue)
                    
            # checks for elements in schemas only
            if isSchema:
                if elt.namespaceURI == XbrlConst.xsd:
                    localName = elt.localName
                    if localName == "schema":
                        XmlValidate.validate(val.modelXbrl, elt)
                        targetNamespace = elt.get("targetNamespace")
                        if targetNamespace is not None:
                            if targetNamespace == "":
                                val.modelXbrl.uuidError("8862e2440a0a4cb38f2697ece64b227a",
                                    modelObject=elt)
                            if val.validateEFM and len(targetNamespace) > 85:
                                l = len(targetNamespace.encode("utf-8"))
                                if l > 255:
                                    val.modelXbrl.uuidError("de94655c13304dc5a8b453fc3a743537",
                                        modelObject=elt, length=l, targetNamespace=targetNamespace)
                        if val.validateSBRNL:
                            if elt.get("targetNamespace") is None:
                                val.modelXbrl.uuidError("6472fb2f36be49acb46f2b530a73ce66",
                                    modelObject=elt)
                            if (elt.get("attributeFormDefault") != "unqualified" or
                                elt.get("elementFormDefault") != "qualified"):
                                val.modelXbrl.uuidError("05ad8135bab545e28cbfa71d202207a5",
                                        modelObject=elt)
                            for attrName in ("blockDefault", "finalDefault", "version"):
                                if elt.get(attrName) is not None:
                                    val.modelXbrl.uuidError("0a2e469041a34e1498c8ea694e1299ac",
                                        modelObject=elt, attribute=attrName)
                    elif val.validateSBRNL:
                        if localName in ("assert", "openContent", "fallback"):
                            val.modelXbrl.uuidError("a170a2ca13ef405e8f99c1403bf4255d",
                                modelObject=elt, element=elt.qname)
                                                    
                        if localName == "element":
                            for attr, presence, errCode in (("block", False, "2.2.2.09"),
                                                            ("final", False, "2.2.2.10"),
                                                            ("fixed", False, "2.2.2.11"),
                                                            ("form", False, "2.2.2.12"),):
                                if (elt.get(attr) is not None) != presence:
                                    val.modelXbrl.error("SBR.NL.{0}".format(errCode),
                                        _('Schema element %(concept)s %(requirement)s contain attribute %(attribute)s'),
                                        modelObject=elt, concept=elt.get("name"), 
                                        requirement=(_("MUST NOT"),_("MUST"))[presence], attribute=attr)
                            eltName = elt.get("name")
                            if eltName is not None: # skip for concepts which are refs
                                type = qname(elt, elt.get("type"))
                                eltQname = elt.qname
                                if type in xsd1_1datatypes:
                                    val.modelXbrl.uuidError("03aa344b279c4306a432259f664d1797",
                                        modelObject=elt, concept=elt.get("name"), xsdType=type)
                                if not parentIsSchema: # root element
                                    if elt.get("name") is not None and (elt.isItem or elt.isTuple):
                                        val.modelXbrl.uuidError("c6061321baf941c2a684e99f370aa147",
                                            modelObject=elt, concept=elt.get("name"))
                                elif eltQname not in val.typedDomainQnames:
                                    for attr, presence, errCode in (("abstract", True, "2.2.2.08"),
                                                                    ("id", True, "2.2.2.13"),
                                                                    ("nillable", True, "2.2.2.15"),
                                                                    ("substitutionGroup", True, "2.2.2.18"),):
                                        if (elt.get(attr) is not None) != presence:
                                            val.modelXbrl.error("SBR.NL.{0}".format(errCode),
                                                _('Schema root element %(concept)s %(requirement)s contain attribute %(attribute)s'),
                                                modelObject=elt, concept=elt.get("name"), 
                                                requirement=(_("MUST NOT"),_("MUST"))[presence], attribute=attr)
                                # semantic checks
                                if elt.isTuple:
                                    val.hasTuple = True
                                    if elt.isAbstract: # root tuple is abstract
                                        val.modelXbrl.uuidError("c9b04918a6d84040a4a544929e894ca5",
                                            modelObject=elt, concept=elt.qname)
                                elif elt.isLinkPart:
                                    val.hasLinkPart = True
                                elif elt.isItem:
                                    if elt.isDimensionItem:
                                        val.hasDimension = True
                                    #elif elt.substitutesFor()
                                    if elt.isAbstract:
                                        val.hasAbstractItem = True
                                    else:
                                        val.hasNonAbstraceElement = True
                                if elt.isAbstract and elt.isItem:
                                    val.hasAbstractItem = True
                                if elt.typeQname is not None:
                                    val.referencedNamespaces.add(elt.typeQname.namespaceURI)
                                if elt.substitutionGroupQname is not None:
                                    val.referencedNamespaces.add(elt.substitutionGroupQname.namespaceURI)
                                if elt.isTypedDimension:
                                    val.referencedNamespaces.add(elt.typedDomainElement.namespaceURI)
                            else:
                                referencedElt = elt.dereference()
                                if referencedElt is not None:
                                    val.referencedNamespaces.add(referencedElt.qname.namespaceURI)
                            if not parentIsSchema:
                                eltDecl = elt.dereference()
                                if (elt.get("minOccurs") is None or elt.get("maxOccurs") is None):
                                    val.modelXbrl.uuidError("d3124e1c2c9e4f1589235aae814453bb",
		                                modelObject=elt, element=eltDecl.qname)
                                elif elt.get("maxOccurs") != "1":
                                    val.modelXbrl.uuidError("ad8f14f8a8df4751a7bfb919f719198d",
	                                    modelObject=elt, concept=eltDecl.qname)
                                if eltDecl.isItem and eltDecl.isAbstract:
                                    val.modelXbrl.uuidError("e7e9332218f3489b9ce4e76509753730",
	                                    modelObject=elt, concept=eltDecl.qname)
                        elif localName in ("sequence","choice"):
                            for attrName in ("minOccurs", "maxOccurs"):
                                attrValue = elt.get(attrName)
                                if  attrValue is None:
                                    val.modelXbrl.uuidError("888b3f5f71ae4c9aad30dcbef6acbbca",
		                                modelObject=elt, element=elt.elementQname, attrName=attrName)
                                elif attrValue != "1":
                                    val.modelXbrl.uuidError("bdac169a84cf437bafd45fab12f872eb",
		                                modelObject=elt, element=elt.elementQname, attrName=attrName)
                        elif localName in {"complexType","simpleType"}:
                            if elt.qnameDerivedFrom is not None:
                                val.referencedNamespaces.add(elt.qnameDerivedFrom.namespaceURI)
                            
                    if localName == "redefine":
                        val.modelXbrl.uuidError("219daef43ae64443aba8a74ecb6f497e",
                            modelObject=elt)
                    if localName in {"attribute", "element", "attributeGroup"}:
                        ref = elt.get("ref")
                        if ref is not None:
                            if qname(elt, ref) not in {"attribute":val.modelXbrl.qnameAttributes, 
                                                       "element":val.modelXbrl.qnameConcepts, 
                                                       "attributeGroup":val.modelXbrl.qnameAttributeGroups}[localName]:
                                val.modelXbrl.uuidError("480d522e8aa24e2bac7633ee32fae77d",
                                    modelObject=elt, element=localName, ref=ref)
                        if val.validateSBRNL and localName == "attribute":
                            val.modelXbrl.uuidError("ab16e657f5c04bfbbad6ac79740251d3",
                                modelObject=elt)
                    if localName == "appinfo":
                        if val.validateSBRNL:
                            if (parent.localName != "annotation" or parent.namespaceURI != XbrlConst.xsd or
                                parent.getparent().localName != "schema" or parent.getparent().namespaceURI != XbrlConst.xsd or
                                XmlUtil.previousSiblingElement(parent) != None):
                                val.modelXbrl.uuidError("36809afa850e4e51a39877c9415639bf",
                                    modelObject=elt)
                            nextSiblingElement = XmlUtil.nextSiblingElement(parent)
                            if nextSiblingElement is not None and nextSiblingElement.localName != "import":
                                val.modelXbrl.uuidError("60a52dfe84e94642b2b82cf78899e705",
                                    modelObject=elt)
                    if localName == "annotation":
                        val.annotationsCount += 1
                        if val.validateSBRNL and not XmlUtil.hasChild(elt,XbrlConst.xsd,"appinfo"):
                            val.modelXbrl.uuidError("c3963d348e6a4d27ac2e0009da42791b",
                                modelObject=elt)
                        
                    if val.validateEFM and localName in {"element", "complexType", "simpleType"}:
                        name = elt.get("name")
                        if name and len(name) > 64:
                            l = len(name.encode("utf-8"))
                            if l > 200:
                                val.modelXbrl.uuidError("578fbc0e5dd34f53bed5923db014e77e",
                                    modelObject=elt, element=localName, name=name, length=l)
    
                    if val.validateSBRNL and localName in {"all", "documentation", "any", "anyAttribute", "attributeGroup",
                                                                # comment out per R.H. 2011-11-16 "complexContent", "complexType", "extension", 
                                                                "field", "group", "key", "keyref",
                                                                "list", "notation", "redefine", "selector", "unique"}:
                        val.modelXbrl.error("SBR.NL.2.2.11.{0:02}".format({"all":1, "documentation":2, "any":3, "anyAttribute":4, "attributeGroup":7,
                                                                  "complexContent":10, "complexType":11, "extension":12, "field":13, "group":14, "key":15, "keyref":16,
                                                                  "list":17, "notation":18, "redefine":20, "selector":22, "unique":23}[localName]),
                            _('Schema file element must not be used "%(element)s"'),
                            modelObject=elt, element=elt.qname)
                    if val.inSchemaTop:
                        if localName in schemaBottom:
                            val.inSchemaTop = False
                    elif localName in schemaTop:
                        val.modelXbrl.uuidError("cf493fb4f68d4a9aaefcc0f2869b4ed5",
                            modelObject=elt, element=elt.prefixedName)
                        
                # check schema roleTypes        
                if elt.localName in ("roleType","arcroleType") and elt.namespaceURI == XbrlConst.link:
                    uriAttr, xbrlSection, roleTypes, localRoleTypes = {
                           "roleType":("roleURI","5.1.3",val.modelXbrl.roleTypes, val.schemaRoleTypes), 
                           "arcroleType":("arcroleURI","5.1.4",val.modelXbrl.arcroleTypes, val.schemaArcroleTypes)
                           }[elt.localName]
                    if not parent.localName == "appinfo" and parent.namespaceURI == XbrlConst.xsd:
                        val.modelXbrl.error("xbrl.{0}:{1}Appinfo".format(xbrlSection,elt.localName),
                            _("%(element)s not child of xsd:appinfo"),
                            modelObject=elt, element=elt.qname)
                    else: # parent is appinfo, element IS in the right location
                        roleURI = elt.get(uriAttr)
                        if roleURI is None or not UrlUtil.isValid(roleURI):
                            val.modelXbrl.error("xbrl.{0}:{1}Missing".format(xbrlSection,uriAttr),
                                _("%(element)s missing or invalid %(attribute)s"),
                                modelObject=elt, element=elt.qname, attribute=uriAttr)
                        if roleURI in localRoleTypes:
                            val.modelXbrl.error("xbrl.{0}:{1}Duplicate".format(xbrlSection,elt.localName),
                                _("Duplicate %(element)s %(attribute)s %(roleURI)s"),
                                modelObject=elt, element=elt.qname, attribute=uriAttr, roleURI=roleURI)
                        else:
                            localRoleTypes[roleURI] = elt
                        for otherRoleType in roleTypes[roleURI]:
                            if elt != otherRoleType and not XbrlUtil.sEqual(val.modelXbrl, elt, otherRoleType):
                                val.modelXbrl.error("xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s not s-equal in %(otherSchema)s"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI,
                                    otherSchema=otherRoleType.modelDocument.basename)
                        if elt.localName == "arcroleType":
                            cycles = elt.get("cyclesAllowed")
                            if cycles not in ("any", "undirected", "none"):
                                val.modelXbrl.error("xbrl.{0}:{1}CyclesAllowed".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s invalid cyclesAllowed %(value)s"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI, value=cycles)
                            if val.validateSBRNL:
                                val.modelXbrl.uuidError("9f40e7133664434dbb628335c389b465",
                                        modelObject=elt, roleURI=roleURI)
                        else: # roleType
                            if val.validateSBRNL:
                                roleTypeModelObject = modelDocument.idObjects.get(elt.get("id"))
                                if roleTypeModelObject is not None and not roleTypeModelObject.genLabel(lang="nl"):
                                    val.modelXbrl.uuidError("f4bb940b7f1c4ea78069fc2c2eb73db4",
                                        modelObject=elt, roleURI=roleURI)
                        if val.validateEFM and len(roleURI) > 85:
                            l = len(roleURI.encode("utf-8"))
                            if l > 255:
                                val.modelXbrl.uuidError("de94655c13304dc5a8b453fc3a743537",
                                    modelObject=elt, element=elt.qname, attribute=uriAttr, length=l, roleURI=roleURI)
                    # check for used on duplications
                    usedOns = set()
                    for usedOn in elt.iterdescendants(tag="{http://www.xbrl.org/2003/linkbase}usedOn"):
                        if isinstance(usedOn,ModelObject):
                            qName = qname(usedOn, XmlUtil.text(usedOn))
                            if qName not in usedOns:
                                usedOns.add(qName)
                            else:
                                val.modelXbrl.error("xbrl.{0}:{1}s-inequality".format(xbrlSection,elt.localName),
                                    _("%(element)s %(roleURI)s usedOn %(value)s on has s-equal duplicate"),
                                    modelObject=elt, element=elt.qname, roleURI=roleURI, value=qName)
                            if val.validateSBRNL:
                                val.valUsedPrefixes.add(qName.prefix)
                                if qName == XbrlConst.qnLinkCalculationLink:
                                    val.modelXbrl.uuidError("73f1273c15b94bd083ad7227f4ca028d",
                                        modelObject=elt, element=parent.qname, value=qName)
                                if elt.localName == "roleType" and qName in XbrlConst.standardExtLinkQnames:
                                    if not any((key[1] == roleURI  and key[2] == qName) 
                                               for key in val.modelXbrl.baseSets.keys()):
                                        val.modelXbrl.uuidError("183db34dff584317b78ffd7befb4981a",
                                            modelObject=elt, element=parent.qname, usedOn=qName, role=roleURI)
                if val.validateSBRNL and not elt.prefix:
                        val.modelXbrl.uuidError("568ca8e58e25498abe58871a306f10b2",
                                modelObject=elt, element=elt.qname)
            elif modelDocument.type == ModelDocument.Type.LINKBASE:
                if elt.localName == "linkbase":
                    XmlValidate.validate(val.modelXbrl, elt)
                if val.validateSBRNL and not elt.prefix:
                        val.modelXbrl.uuidError("a54e29cf5fbf48039fc7f117eb8abe72",
                            modelObject=elt, element=elt.qname)
            # check of roleRefs when parent is linkbase or instance element
            xlinkType = elt.get("{http://www.w3.org/1999/xlink}type")
            xlinkRole = elt.get("{http://www.w3.org/1999/xlink}role")
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName == "linkbase":
                    if elt.parentQname not in (None, XbrlConst.qnXsdAppinfo):
                        val.modelXbrl.uuidError("d77dbedf68da4911b0aa580f1db6675c",
                            parent=elt.parentQname,
                            modelObject=elt)
                elif elt.localName in ("roleRef","arcroleRef"):
                    uriAttr, xbrlSection, roleTypeDefs, refs = {
                           "roleRef":("roleURI","3.5.2.4",val.modelXbrl.roleTypes,val.roleRefURIs), 
                           "arcroleRef":("arcroleURI","3.5.2.5",val.modelXbrl.arcroleTypes,val.arcroleRefURIs)
                           }[elt.localName]
                    if parentIsAppinfo:
                        pass    #ignore roleTypes in appinfo (test case 160 v05)
                    elif not (parentIsLinkbase or isInstance):
                        val.modelXbrl.info("info:{1}Location".format(xbrlSection,elt.localName),
                            _("Link:%(elementName)s not child of link:linkbase or xbrli:instance"),
                            modelObject=elt, elementName=elt.localName)
                    else: # parent is linkbase or instance, element IS in the right location
        
                        # check for duplicate roleRefs when parent is linkbase or instance element
                        refUri = elt.get(uriAttr)
                        hrefAttr = elt.get("{http://www.w3.org/1999/xlink}href")
                        hrefUri, hrefId = UrlUtil.splitDecodeFragment(hrefAttr)
                        if refUri == "":
                            val.modelXbrl.error("xbrl.3.5.2.4.5:{0}Missing".format(elt.localName),
                                _("%(element)s %(refURI)s missing"),
                                modelObject=elt, element=elt.qname, refURI=refUri)
                        elif refUri in refs:
                            val.modelXbrl.error("xbrl.3.5.2.4.5:{0}Duplicate".format(elt.localName),
                                _("%(element)s is duplicated for %(refURI)s"),
                                modelObject=elt, element=elt.qname, refURI=refUri)
                        elif refUri not in roleTypeDefs:
                            val.modelXbrl.error("xbrl.3.5.2.4.5:{0}NotDefined".format(elt.localName),
                                _("%(element)s %(refURI)s is not defined"),
                                modelObject=elt, element=elt.qname, refURI=refUri)
                        else:
                            refs[refUri] = hrefUri
                        
                        if val.validateDisclosureSystem:
                            if elt.localName == "arcroleRef":
                                if hrefUri not in val.disclosureSystem.standardTaxonomiesDict:
                                    val.modelXbrl.uuidError("7a5cf9f5f23e4859af3d6926cb4f89e5",
                                        modelObject=elt, refURI=refUri, xlinkHref=hrefUri)
                                if val.validateSBRNL:
                                    for attrName, errUuid in (("{http://www.w3.org/1999/xlink}arcrole","bdf2017b706742b28c074f03e0a2d353"),("{http://www.w3.org/1999/xlink}role","08c0ee1cd67d4e04a4432cf2acde15ab")):
                                        if elt.get(attrName):
                                            val.modelXbrl.uuidError(errUuid,
                                                modelObject=elt, refURI=refUri, xlinkHref=hrefUri, attribute=attrName)
                            elif elt.localName == "roleRef":
                                if val.validateSBRNL:
                                    for attrName, errUuid in (("{http://www.w3.org/1999/xlink}arcrole","e8188bcfa14746b2b0ae9d419db833dd"),("{http://www.w3.org/1999/xlink}role","76edd41a9ff94dbdb979477858862ae7")):
                                        if elt.get(attrName):
                                            val.modelXbrl.uuidError(errUuid,
                                                modelObject=elt, refURI=refUri, xlinkHref=hrefUri, attribute=attrName)
                    if val.validateSBRNL:
                        if not xlinkType:
                            val.modelXbrl.uuidError("43ea6adc66ae4c2ea9defc4b6fbaf02d",
                                modelObject=elt)
    
            # checks for elements in linkbases
            if elt.namespaceURI == XbrlConst.link:
                if elt.localName in ("schemaRef", "linkbaseRef", "roleRef", "arcroleRef"):
                    if xlinkType != "simple":
                        val.modelXbrl.uuidError("79ccb3bf8bd347a99ce5c642422b8e95",
                            modelObject=elt, element=elt.qname)
                    href = elt.get("{http://www.w3.org/1999/xlink}href")
                    if not href or "xpointer(" in href:
                        val.modelXbrl.uuidError("a08a91248ffc4f1eb682d64e7dbc7cad",
                            modelObject=elt, element=elt.qname)
                    for name in ("{http://www.w3.org/1999/xlink}role", "{http://www.w3.org/1999/xlink}arcrole"):
                        if elt.get(name) == "":
                            val.modelXbrl.error("xbrl.3.5.1.2:simpleLink" + name,
                                _("Element %(element)shas empty %(attribute)s"),
                                modelObject=elt, attribute=name)
                    if elt.localName == "linkbaseRef" and \
                        elt.get("{http://www.w3.org/1999/xlink}arcrole") != XbrlConst.xlinkLinkbase:
                            val.modelXbrl.uuidError("919596a9f21e44d49bcbc7379f584c48",
                                modelObject=elt)
                elif elt.localName == "loc":
                    if xlinkType != "locator":
                        val.modelXbrl.uuidError("d70c7bd71cd4415b8ff7fceb1a6249d3",
                            modelObject=elt, element=elt.qname)
                    for name, errUuid in (("{http://www.w3.org/1999/xlink}href","2a797c026d5849de90c9256393cd51bf"),
                                          ("{http://www.w3.org/1999/xlink}label","f1b9f4fc3a9b4e71bc36c8a462e1427c")):
                        if elt.get(name) is None:
                            val.modelXbrl.uuidError(errUuid,
                                modelObject=elt, element=elt.qname, attribute=name)
                elif xlinkType == "resource":
                    if elt.localName == "footnote" and elt.get("{http://www.w3.org/XML/1998/namespace}lang") is None:
                        val.modelXbrl.uuidError("0e1f16b9f7964c2d8dca30a225ef50cc",
                            modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                    elif elt.localName == "footnote" and elt.get("{http://www.w3.org/XML/1998/namespace}lang") is None:
                        val.modelXbrl.uuidError("fb34a9dff6b2416ea8abfaea0a675d06",
                            modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                    if val.validateSBRNL:
                        if elt.localName in ("label", "reference"):
                            if not XbrlConst.isStandardRole(xlinkRole):
                                val.modelXbrl.uuidError("d16ec72ce03d4675ada45c9c756092cf",
                                    modelObject=elt, element=elt.elementQname, xlinkRole=xlinkRole)
                        if elt.localName == "reference": # look for custom reference parts
                            for linkPart in elt.iterchildren():
                                if linkPart.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
                                    val.modelXbrl.uuidError("3a0075459ad24cc2af78d71fd9cb731a",
                                        modelObject=linkPart, element=linkPart.elementQname)
                    # TBD: add lang attributes content validation
            if xlinkRole is not None:
                if xlinkRole == "" and xlinkType == "simple":
                    val.modelXbrl.uuidError("b658a1879a904ab7821372b6fd188dc6",
                        modelObject=elt, xlinkRole=xlinkRole)
                elif xlinkRole == "" and xlinkType == "extended" and \
                     XbrlConst.isStandardResourceOrExtLinkElement(elt):
                    val.modelXbrl.uuidError("551312e6f2f64d6985bdf8de5dcfd031",
                        modelObject=elt, xlinkRole=xlinkRole)
                elif not xlinkRole.startswith("http://"):
                    if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                        val.modelXbrl.uuidError("8192fd3302ad4c068542248ec318c866",
                            modelObject=elt, xlinkRole=xlinkRole)
                    elif val.isGenericLink(elt):
                        val.modelXbrl.uuidError("f1579aaa71b246aab8549970ec1c9f1b",
                            modelObject=elt, xlinkRole=xlinkRole)
                    elif val.isGenericResource(elt):
                        val.modelXbrl.uuidError("771bdf7f54934fa299169f72bce4cbb4",
                            modelObject=elt, xlinkRole=xlinkRole)
                elif not XbrlConst.isStandardRole(xlinkRole):
                    if xlinkRole not in val.roleRefURIs:
                        if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                            val.modelXbrl.uuidError("78ccf8c2d7e643ceb5965bd26754cdcd",
                                modelObject=elt, xlinkRole=xlinkRole)
                        elif val.isGenericLink(elt):
                            val.modelXbrl.uuidError("beaf4e4847044b8b94710b3181d2f13d",
                                modelObject=elt, xlinkRole=xlinkRole)
                        elif val.isGenericResource(elt):
                            val.modelXbrl.uuidError("5bd78117a74e44f8a6084e51b25ff0a1",
                                modelObject=elt, xlinkRole=xlinkRole)
                    modelsRole = val.modelXbrl.roleTypes.get(xlinkRole)
                    if modelsRole is None or len(modelsRole) == 0 or qname(elt) not in modelsRole[0].usedOns:
                        if XbrlConst.isStandardResourceOrExtLinkElement(elt):
                            val.modelXbrl.uuidError("0e60185137d0490ca29fc827a67b9563",
                                modelObject=elt, xlinkRole=xlinkRole, element=elt.qname)
                        elif val.isGenericLink(elt):
                            val.modelXbrl.uuidError("91c6a1031ec845498f69db0706e10f82",
                                modelObject=elt, xlinkRole=xlinkRole, element=elt.qname)
                        elif val.isGenericResource(elt):
                            val.modelXbrl.uuidError("a063247e11aa4f1c96499857a6618310",
                                modelObject=elt, xlinkRole=xlinkRole, element=elt.qname)
            elif xlinkType == "extended" and val.validateSBRNL: # no @role on extended link
                val.modelXbrl.uuidError("bc10848450c94d09bcfeb2327eb0eac0",
                    modelObject=elt, element=elt.elementQname)
            if elt.get("{http://www.w3.org/1999/xlink}arcrole") is not None:
                arcrole = elt.get("{http://www.w3.org/1999/xlink}arcrole")
                if arcrole == "" and \
                    elt.get("{http://www.w3.org/1999/xlink}type") == "simple":
                    val.modelXbrl.uuidError("62e8c1f301374f90ad444b7536311b41",
                        modelObject=elt, element=elt.qname)
                elif not arcrole.startswith("http://"):
                    if XbrlConst.isStandardArcInExtLinkElement(elt):
                        val.modelXbrl.uuidError("7de59a21abe649cf831bd26e75a79770",
                            modelObject=elt, element=elt.qname, arcrole=arcrole)
                    elif val.isGenericArc(elt):
                        val.modelXbrl.uuidError("1f7f5af249d54c569c2dc450cdb808b6",
                            modelObject=elt, element=elt.qname, arcrole=arcrole)
                elif not XbrlConst.isStandardArcrole(arcrole):
                    if arcrole not in val.arcroleRefURIs:
                        if XbrlConst.isStandardArcInExtLinkElement(elt):
                            val.modelXbrl.uuidError("921b62424daa41f0aa75bbfe8c8bb12b",
                                modelObject=elt, element=elt.qname, arcrole=arcrole)
                        elif val.isGenericArc(elt):
                            val.modelXbrl.uuidError("f3ec328d483e4997ac4edad220c70e3d",
                                modelObject=elt, element=elt.qname, arcrole=arcrole)
                    modelsRole = val.modelXbrl.arcroleTypes.get(arcrole)
                    if modelsRole is None or len(modelsRole) == 0 or qname(elt) not in modelsRole[0].usedOns:
                        if XbrlConst.isStandardArcInExtLinkElement(elt):
                            val.modelXbrl.uuidError("57de3ac55b56426888114eb6b6ce0fc9",
                                modelObject=elt, element=elt.qname, arcrole=arcrole)
                        elif val.isGenericArc(elt):
                            val.modelXbrl.uuidError("96f5504922564fa3bea8259bb987f765",
                                modelObject=elt, element=elt.qname, arcrole=arcrole)
                elif XbrlConst.isStandardArcElement(elt):
                    if XbrlConst.standardArcroleArcElement(arcrole) != elt.localName:
                        val.modelXbrl.uuidError("f2dedbbafbbd490da82956599a100d44",
                            modelObject=elt, element=elt.qname, arcrole=arcrole)
    
            #check resources
            if parentXlinkType == "extended":
                if elt.localName not in ("documentation", "title") and \
                    xlinkType not in ("arc", "locator", "resource"):
                    val.modelXbrl.uuidError("ef2c35f8e33f4a199a3cc2162c33a883",
                        modelObject=elt, element=elt.qname)
            if xlinkType == "resource":
                if not elt.get("{http://www.w3.org/1999/xlink}label"):
                    val.modelXbrl.uuidError("c2d7d21475644f19a7f7a0a9d6e551a8",
                        modelObject=elt, element=elt.qname)
            elif xlinkType == "arc":
                for name, errUuid in (("{http://www.w3.org/1999/xlink}from", "63fee5da01dc48b9a4e3b4b32c7dd1a5"),
                                      ("{http://www.w3.org/1999/xlink}to", "17056b25a609463e89ecc0ceb0cdf12a")):
                    if not elt.get(name):
                        val.modelXbrl.uuidError(errUuid,
                            modelObject=elt, element=elt.qname, attribute=name)
                if val.modelXbrl.hasXDT and elt.get("{http://xbrl.org/2005/xbrldt}targetRole") is not None:
                    targetRole = elt.get("{http://xbrl.org/2005/xbrldt}targetRole")
                    if not XbrlConst.isStandardRole(targetRole) and \
                       targetRole not in val.roleRefURIs:
                        val.modelXbrl.uuidError("6858185ae366424dac7f3bd7d62d3038",
                            modelObject=elt, element=elt.qname, targetRole=targetRole)
                val.containsRelationship = True
            xmlLang = elt.get("{http://www.w3.org/XML/1998/namespace}lang")
            if val.validateXmlLang and xmlLang is not None:
                if not val.disclosureSystem.xmlLangPattern.match(xmlLang):
                    val.modelXbrl.uuidError("f707812b10b44046b2b2879072a4e934" if (val.validateSBRNL and xmlLang.startswith('nl')) else \
                        "87abecdc569a4e9fa9e2c90a08f8f129" if (val.validateSBRNL and xmlLang.startswith('en')) else "29f2e7ad33d04f16ac08a73c3afeb984",
                        modelObject=elt, element=elt.qname,
                        xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"),
                        lang=elt.get("{http://www.w3.org/XML/1998/namespace}lang"))
                 
            if isInstance:
                if elt.namespaceURI == XbrlConst.xbrli:
                    expectedSequence = instanceSequence.get(elt.localName,9)
                else:
                    expectedSequence = 9    #itdms last
                if instanceOrder > expectedSequence:
                    val.modelXbrl.uuidError("88323bacfc6e430aabfae0de55d86fa9",
                        modelObject=elt, element=elt.qname)
                else:
                    instanceOrder = expectedSequence

            if modelDocument.type == ModelDocument.Type.Unknown:
                if elt.localName == "xbrl" and elt.namespaceURI == XbrlConst.xbrli:
                    if elt.getparent() is not None:
                        val.modelXbrl.uuidError("37e35e0702e84e1593293c30763491c6",
                            parent=elt.parentQname,
                            modelObject=elt)
                elif elt.localName == "schema" and elt.namespaceURI == XbrlConst.xsd:
                    if elt.getparent() is not None:
                        val.modelXbrl.uuidError("d20351a8b8c64896a3fb27c24f5d016c",
                            parent=elt.parentQname,
                            modelObject=elt)
                    
            if modelDocument.type == ModelDocument.Type.INLINEXBRL:
                if elt.namespaceURI == XbrlConst.ixbrl and val.validateGFM:
                    if elt.localName == "footnote":
                        if elt.get("{http://www.w3.org/1999/xlink}arcrole") != XbrlConst.factFootnote:
                            # must be in a nonDisplay div
                            inNondisplayDiv = False
                            ancestor = elt.getparent()
                            while ancestor is not None:
                                if (ancestor.localName == "div" and ancestor.namespaceURI == XbrlConst.xhtml and 
                                    ancestor.get("style") == "display:none"):
                                    inNondisplayDiv = True
                                    break
                                ancestor = ancestor.getparent()
                            if not inNondisplayDiv:
                                val.modelXbrl.uuidError("4a4a588bd4fc41e2a3fdc33b27ad4075",
                                    modelObject=elt, footnoteID=elt.get("footnoteID"), 
                                    arcrole=elt.get("{http://www.w3.org/1999/xlink}arcrole"))
                        id = elt.get("footnoteID")
                        if id not in val.footnoteRefs and XmlUtil.innerText(elt):
                            val.modelXbrl.uuidError("1ca0f77038f4492ca7100b6e52697140",
                                modelObject=elt, footnoteID=id)
                            
                        if not elt.get("{http://www.w3.org/XML/1998/namespace}lang"):
                            val.modelXbrl.uuidError("5f1baf08cbac41d181b233c5d3ef3346",
                                modelObject=elt, footnoteID=id)
                        
            if val.validateDisclosureSystem:
                if xlinkType == "extended":
                    if not xlinkRole or xlinkRole == "":
                        val.modelXbrl.uuidError("e0b220f502c44a1cb8f50477a9f05495",
                            modelObject=elt, element=elt.qname)
                    eltNsName = (elt.namespaceURI,elt.localName)
                    if not val.extendedElementName:
                        val.extendedElementName = elt.qname
                    elif val.extendedElementName != elt.qname:
                        val.modelXbrl.uuidError("e0855636043a4398a8d54704468f6bb0",
                            modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                if xlinkType == "locator":
                    if val.validateSBRNL and elt.qname != XbrlConst.qnLinkLoc:
                        val.modelXbrl.uuidError("8f1b894538ed439294fc6730cbcd6a48",
                            modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                if xlinkType == "resource":
                    if not xlinkRole:
                        val.modelXbrl.uuidError("e0b220f502c44a1cb8f50477a9f05495",
                            modelObject=elt, element=elt.qname)
                    elif not (XbrlConst.isStandardRole(xlinkRole) or 
                              val.roleRefURIs.get(xlinkRole) in val.disclosureSystem.standardTaxonomiesDict):
                        val.modelXbrl.uuidError("c7aa115b71094c92bc3955ac4234e950",
                            modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"), role=xlinkRole)
                    if val.validateSBRNL:
                        if elt.localName == "reference":
                            for child in elt.iterdescendants():
                                if isinstance(child,ModelObject) and child.namespaceURI.startswith("http://www.xbrl.org") and child.namespaceURI != "http://www.xbrl.org/2006/ref":
                                    val.modelXbrl.uuidError("5b8ac27fd430444e8f04f8cd53e07a2d",
                                        modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"), 
                                        element=qname(child))
                            id = elt.get("id")
                            if not id:
                                val.modelXbrl.uuidError("e82be62fab8b4b2a903e15d5e627c081",
                                    modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                            elif id in val.DTSreferenceResourceIDs:
                                val.modelXbrl.uuidError("663f9ef0a709419e83a08e96b39ec408",
                                    modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"),
                                    id=id, otherLinkbase=val.DTSreferenceResourceIDs[id])
                            else:
                                val.DTSreferenceResourceIDs[id] = modelDocument.basename
                        if elt.qname not in {
                            XbrlConst.qnLinkLabelLink: (XbrlConst.qnLinkLabel,),
                            XbrlConst.qnLinkReferenceLink: (XbrlConst.qnLinkReference,),
                            XbrlConst.qnLinkPresentationLink: tuple(),
                            XbrlConst.qnLinkCalculationLink: tuple(),
                            XbrlConst.qnLinkDefinitionLink: tuple(),
                            XbrlConst.qnLinkFootnoteLink: (XbrlConst.qnLinkFootnote,),
                            XbrlConst.qnGenLink: (XbrlConst.qnGenLabel, XbrlConst.qnGenReference, val.qnSbrLinkroleorder),
                             }.get(val.extendedElementName,tuple()):
                            val.modelXbrl.uuidError("984d3b421382432dbd527a7687545c54",
                                modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                if xlinkType == "arc":
                    if elt.get("priority") is not None:
                        priority = elt.get("priority")
                        try:
                            if int(priority) >= 10:
                                val.modelXbrl.uuidError("d49714f3afb44071a64f39fe878447f0",
                                    modelObject=elt, 
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                    priority=priority)
                        except (ValueError) :
                            val.modelXbrl.uuidError("d4b9c600765d4c2f957718e9cd2a3d71",
                                modelObject=elt, 
                                xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                priority=priority)
                    if elt.namespaceURI == XbrlConst.link:
                        if elt.localName == "presentationArc" and not elt.get("order"):
                            val.modelXbrl.uuidError("58533bed127a4c73b82a07e8a5f48844",
                                modelObject=elt, 
                                xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                        elif elt.localName == "calculationArc":
                            if not elt.get("order"):
                                val.modelXbrl.uuidError("4f4d710cae83459f8f8c61397c163fa6",
                                    modelObject=elt, 
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                            try:
                                weight = float(elt.get("weight"))
                                if not weight in (1, -1):
                                    val.modelXbrl.uuidError("2c93c771afdf491bb08c7ac4cf70f5c6",
                                        modelObject=elt, 
                                        xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                        xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"),
                                        weight=weight)
                            except ValueError:
                                val.modelXbrl.uuidError("bde90a2b3b584e9c8de3c746eb2b6fc4",
                                    modelObject=elt, 
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                        elif elt.localName == "definitionArc":
                            if not elt.get("order"):
                                val.modelXbrl.uuidError("eba246b8ce524e0593bd8a1b360acd22",
                                    modelObject=elt, 
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                            if val.validateSBRNL and arcrole in (XbrlConst.essenceAlias, XbrlConst.similarTuples, XbrlConst.requiresElement):
                                val.modelXbrl.uuidError({XbrlConst.essenceAlias: "e59bace33210446cae1cc755e0ca6abf",
                                                  XbrlConst.similarTuples: "8c0bb9e3c04641b895ae1f4c21a6fb3d",
                                                  XbrlConst.requiresElement: "95384baa3b6f4bcfaf3d30019e76207e"}[arcrole],
                                    modelObject=elt, 
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"), 
                                    arcrole=arcrole), 
                        elif elt.localName == "referenceArc" and val.validateSBRNL:
                            if elt.get("order"):
                                val.modelXbrl.uuidError("2e14f86c80ff4783981f9d476ef4cae1",
                                    modelObject=elt, 
                                    xlinkFrom=elt.get("{http://www.w3.org/1999/xlink}from"),
                                    xlinkTo=elt.get("{http://www.w3.org/1999/xlink}to"))
                        if val.validateSBRNL and elt.get("use") == "prohibited" and elt.getparent().tag in (
                                "{http://www.xbrl.org/2003/linkbase}presentationLink", 
                                "{http://www.xbrl.org/2003/linkbase}labelLink", 
                                "{http://xbrl.org/2008/generic}link", 
                                "{http://www.xbrl.org/2003/linkbase}referenceLink"):
                            val.modelXbrl.uuidError("cd834eb5edc546e8bc2846e4c9ef6e68",
                                modelObject=elt, arc=elt.getparent().qname)
                    if val.validateSBRNL and elt.qname not in {
                        XbrlConst.qnLinkLabelLink: (XbrlConst.qnLinkLabelArc,),
                        XbrlConst.qnLinkReferenceLink: (XbrlConst.qnLinkReferenceArc,),
                        XbrlConst.qnLinkPresentationLink: (XbrlConst.qnLinkPresentationArc,),
                        XbrlConst.qnLinkCalculationLink: (XbrlConst.qnLinkCalculationArc,),
                        XbrlConst.qnLinkDefinitionLink: (XbrlConst.qnLinkDefinitionArc,),
                        XbrlConst.qnLinkFootnoteLink: (XbrlConst.qnLinkFootnoteArc,),
                        XbrlConst.qnGenLink: (XbrlConst.qnGenArc,),
                         }.get(val.extendedElementName, tuple()):
                        val.modelXbrl.uuidError("2d2641a76ba1484081ba16cfae450857",
                            modelObject=elt, element=elt.qname, element2=val.extendedElementName)
                    if val.validateSBRNL and elt.qname == XbrlConst.qnLinkLabelArc and elt.get("order"):
                        val.modelXbrl.uuidError("bf756346fb364ca0a6d06a4b5cba73fa",
                            modelObject=elt, order=elt.get("order"))
                if val.validateSBRNL:
                    # check attributes for prefixes and xmlns
                    val.valUsedPrefixes.add(elt.prefix)
                    if elt.namespaceURI not in val.disclosureSystem.baseTaxonomyNamespaces:
                        val.modelXbrl.uuidError("2bd23e5b3cb440fb8cf0a7306bdcb6d3",
                            modelObject=elt, element=elt.qname, 
                            fileType="schema" if isSchema else "linkbase" ,
                            namespace=elt.namespaceURI)
                    for attrTag, attrValue in elt.items():
                        prefix, ns, localName = XmlUtil.clarkNotationToPrefixNsLocalname(elt, attrTag, isAttribute=True)
                        if prefix: # don't count unqualified prefixes for using default namespace
                            val.valUsedPrefixes.add(prefix)
                        if ns and ns not in val.disclosureSystem.baseTaxonomyNamespaces:
                            val.modelXbrl.uuidError("34d17694f21f4f13ae58d2fca1e71761",
                                modelObject=elt, element=elt.qname, 
                                fileType="schema" if isSchema else "linkbase" ,
                                prefix=prefix, localName=localName)
                        if isSchema and localName in ("base", "ref", "substitutionGroup", "type"):
                            valuePrefix, sep, valueName = attrValue.partition(":")
                            if sep:
                                val.valUsedPrefixes.add(valuePrefix)
                    # check for xmlns on a non-root element
                    parentElt = elt.getparent()
                    if parentElt is not None:
                        for prefix, ns in elt.nsmap.items():
                            if prefix not in parentElt.nsmap or parentElt.nsmap[prefix] != ns:
                                val.modelXbrl.uuidError("9b48a19662ae4a0ab679bb8bc511c472" if isSchema else "6765ebbbeeda418fa56b627a43e2a650",
                                    modelObject=elt, element=elt.qname, 
                                    fileType="schema" if isSchema else "linkbase" ,
                                    prefix=prefix)
                            
                    if elt.localName == "roleType" and not elt.get("id"): 
                        val.modelXbrl.uuidError("a199d368003441c1b46157d0e53a8c0c",
                            modelObject=elt, roleURI=elt.get("roleURI"))
                    elif elt.localName == "loc" and elt.get("{http://www.w3.org/1999/xlink}role"): 
                        val.modelXbrl.uuidError("8d975fa8e203436e8ee54a639d2cafdb",
                            modelObject=elt, xlinkLabel=elt.get("{http://www.w3.org/1999/xlink}label"))
                    elif elt.localName == "documentation": 
                        val.modelXbrl.uuidError("bc6a5713e88d4367b69916dd702e00cb",
                            modelObject=elt, value=XmlUtil.text(elt))
                    if elt.localName == "linkbase":
                        schemaLocation = elt.get("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation")
                        if schemaLocation:
                            schemaLocations = schemaLocation.split()
                            for sl in (XbrlConst.link, XbrlConst.xlink):
                                if sl in schemaLocations:
                                    val.modelXbrl.uuidError("33db11d07fbc4debb475c7a4bf7481a7",
                                        modelObject=elt, schemaLocation=sl)
                        for attrName, errUuid in (("id", "1f4ba7d1181049bf928e7653469ff642"),
                                                  ("{http://www.w3.org/2001/XMLSchema-instance}nil", "0a9445cf2036483a9e2f42a2e8e18d97"),
                                                  ("{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation", "6577877df0324b1895f854e4e263d019"),
                                                  ("{http://www.w3.org/2001/XMLSchema-instance}type", "8db9011a74c94b9a8abd66092830f391")):
                            if elt.get(attrName) is not None: 
                                val.modelXbrl.uuidError(errUuid,
                                    modelObject=elt, element=elt.qname, attribute=attrName)
                    for attrName, errUuid in (("{http://www.w3.org/1999/xlink}actuate", "39543ba11fe844afbb9733ce9908529d"),
                                              ("{http://www.w3.org/1999/xlink}show", "9038bf6742c2414196d030749794a035"),
                                              ("{http://www.w3.org/1999/xlink}title", "dedc257c5b0c454097493ef439657e38")):
                        if elt.get(attrName) is not None: 
                            val.modelXbrl.uuidError(errUuid,
                                modelObject=elt, element=elt.qname, attribute=attrName)
    
            checkElements(val, modelDocument, elt)
        elif isinstance(elt,ModelComment): # comment node
            if val.validateSBRNL:
                if elt.itersiblings(preceding=True):
                    val.modelXbrl.uuidError("c4fc6a958cc740bc90d1b6a8b6939972" if isSchema else "f59a0a6dc7d74ddba9079f16e7bbb2d1",
                            modelObject=elt, fileType=modelDocument.gettype().title(), value=elt.text)

    # dereference at end of processing children of instance linkbase
    if isInstance or parentIsLinkbase:
        val.roleRefURIs = {}
        val.arcroleRefURIs = {}


