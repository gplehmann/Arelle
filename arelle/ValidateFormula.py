'''
Created on Dec 9, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import os
from collections import defaultdict
from arelle.pyparsing.pyparsing_py3 import (ParseException) 
from arelle.ModelFormulaObject import (ModelParameter, ModelInstance, ModelVariableSet,
                                       ModelFormula, ModelTuple, ModelVariable, ModelFactVariable, 
                                       ModelVariableSetAssertion, ModelConsistencyAssertion,
                                       ModelExistenceAssertion, ModelValueAssertion,
                                       ModelPrecondition, ModelConceptName, Trace,
                                       Aspect, aspectModels, ModelAspectCover)
from arelle.ModelObject import (ModelObject)
from arelle.ModelValue import (qname,QName)
from arelle import (XbrlConst, XmlUtil, ModelXbrl, ModelDocument, XPathParser, XPathContext, FunctionXs,
                    ValidateXbrlDimensions) 

arcroleChecks = {
    XbrlConst.equalityDefinition:   (None, 
                                     XbrlConst.qnEqualityDefinition, 
                                     "xbrlve:info"),
    XbrlConst.assertionSet:          (XbrlConst.qnAssertionSet,
                                      (XbrlConst.qnAssertion, XbrlConst.qnVariableSetAssertion),
                                      "xbrlvalide:info"),
    XbrlConst.variableSet:           (XbrlConst.qnVariableSet,
                                      (XbrlConst.qnVariableVariable, XbrlConst.qnParameter),
                                      "xbrlve:info"),
    XbrlConst.variableSetFilter:    (XbrlConst.qnVariableSet, 
                                     XbrlConst.qnVariableFilter, 
                                     "xbrlve:info"),
    XbrlConst.variableFilter:       (XbrlConst.qnFactVariable, 
                                     XbrlConst.qnVariableFilter, 
                                     "xbrlve:info"),
    XbrlConst.booleanFilter:        (XbrlConst.qnVariableFilter, 
                                     XbrlConst.qnVariableFilter, 
                                     "xbrlbfe:info"),
   XbrlConst.consistencyAssertionFormula:       (XbrlConst.qnConsistencyAssertion, 
                                                 None, 
                                     "xbrlca:info"),
    XbrlConst.functionImplementation: (XbrlConst.qnCustomFunctionSignature,
                                      XbrlConst.qnCustomFunctionImplementation,
                                      "xbrlcfie:info"),
    }
def checkBaseSet(val, arcrole, ELR, relsSet):
    # check hypercube-dimension relationships
     
    if arcrole in arcroleChecks:
        fromQname, toQname, errCode = arcroleChecks[arcrole]
        for modelRel in relsSet.modelRelationships:
            fromMdlObj = modelRel.fromModelObject
            toMdlObj = modelRel.toModelObject
            if fromQname:
                if fromMdlObj is None or not val.modelXbrl.isInSubstitutionGroup(fromMdlObj.elementQname, fromQname):
                    val.modelXbrl.info(errCode,
                        _("Relationship from %(xlinkFrom)s to %(xlinkTo)s should have an %(element)s source"),
                        modelObject=modelRel, xlinkFrom=modelRel.fromLabel, xlinkTo=modelRel.toLabel, element=fromQname)
            if toQname:
                if toMdlObj is None or not val.modelXbrl.isInSubstitutionGroup(toMdlObj.elementQname, toQname):
                    val.modelXbrl.info(errCode,
                        _("Relationship from %(xlinkFrom)s to %(xlinkTo)s should have an %(element)s  target"),
                        modelObject=modelRel, xlinkFrom=modelRel.fromLabel, xlinkTo=modelRel.toLabel, element=toQname)
    if arcrole == XbrlConst.functionImplementation:
        for relFrom, rels in relsSet.fromModelObjects().items():
            if len(rels) > 1:
                val.modelXbrl.uuidError("807c98f0916d4382985cade105e61224",
                     modelObject=modelRel, name=relFrom.name)
        for relTo, rels in relsSet.toModelObjects().items():
            if len(rels) > 1:
                val.modelXbrl.uuidError("4595e809bc57461bb545314aa3580263",
                    modelObject=modelRel, xlinkLabel=relTo.xlinkLabel)
                
def executeCallTest(val, name, callTuple, testTuple):
    if callTuple:
        XPathParser.initializeParser(val)
        
        try:                            
            val.modelXbrl.modelManager.showStatus(_("Executing call"))
            callExprStack = XPathParser.parse(val, callTuple[0], callTuple[1], name + " call", Trace.CALL)
            xpathContext = XPathContext.create(val.modelXbrl, sourceElement=callTuple[1])
            result = xpathContext.evaluate(callExprStack)
            xpathContext.inScopeVars[qname('result',noPrefixIsNoNamespace=True)] = result 
            val.modelXbrl.uuidInfo("f67a61fcc1974a7081ea14f641c01ec9",
                               modelObject=callTuple[1], name=name, result=str(result))
            
            if testTuple:
                val.modelXbrl.modelManager.showStatus(_("Executing test"))
                testExprStack = XPathParser.parse(val, testTuple[0], testTuple[1], name + " test", Trace.CALL)
                testResult = xpathContext.effectiveBooleanValue( None, xpathContext.evaluate(testExprStack) )
                
                if testResult:
                    val.modelXbrl.uuidInfo("54c23dba54884d1789cf049155b4d732",
                                       modelObject=testTuple[1], name=name, result=str(testResult))
                else:
                    val.modelXbrl.uuidError("d95199f90e994139a1cf9b587e80e69c",
                                        modelObject=testTuple[1], name=name, result=str(testResult))
        except XPathContext.XPathException as err:
            val.modelXbrl.error(err.code,
                _("%(name)s evaluation error: %(error)s \n%(errorSource)s"),
                modelObject=callTuple[1], name=name, error=err.message, errorSource=err.sourceErrorIndication)

        val.modelXbrl.modelManager.showStatus(_("ready"), 2000)
                
def validate(val):
    for e in ("xbrl.5.1.4.3:cycles", "xbrlgene:violatedCyclesConstraint"):
        if e in val.modelXbrl.errors:
            val.modelXbrl.uuidInfo("ada6ec06504d4cbba77721e902e0bd73",
                                modelObject=val.modelXbrl, error=e)
            return
    
    formulaOptions = val.modelXbrl.modelManager.formulaOptions
    XPathParser.initializeParser(val)
    val.modelXbrl.modelManager.showStatus(_("Compiling formulae"))
    initialErrorCount = val.modelXbrl.logCountErr
    
    # global parameter names
    parameterQnames = set()
    instanceQnames = set()
    parameterDependencies = {}
    instanceDependencies = defaultdict(set)  # None-key entries are non-formula dependencies
    dependencyResolvedParameters = set()
    orderedParameters = []
    orderedInstances = []
    for paramQname, modelParameter in val.modelXbrl.qnameParameters.items():
        if isinstance(modelParameter, ModelParameter):
            modelParameter.compile()
            parameterDependencies[paramQname] = modelParameter.variableRefs()
            parameterQnames.add(paramQname)
            if isinstance(modelParameter, ModelInstance):
                instanceQnames.add(paramQname)
            # duplicates checked on loading modelDocument
            
    #resolve dependencies
    resolvedAParameter = True
    while (resolvedAParameter):
        resolvedAParameter = False
        for paramQname in parameterQnames:
            if paramQname not in dependencyResolvedParameters and \
               len(parameterDependencies[paramQname] - dependencyResolvedParameters) == 0:
                dependencyResolvedParameters.add(paramQname)
                orderedParameters.append(paramQname)
                resolvedAParameter = True
    # anything unresolved?
    for paramQname in parameterQnames:
        if paramQname not in dependencyResolvedParameters:
            circularOrUndefDependencies = parameterDependencies[paramQname] - dependencyResolvedParameters
            undefinedVars = circularOrUndefDependencies - parameterQnames 
            paramsCircularDep = circularOrUndefDependencies - undefinedVars
            if len(undefinedVars) > 0:
                val.modelXbrl.uuidError("05ba9483354d4ce29a7f993b3be25872",
                    modelObject=val.modelXbrl.qnameParameters[paramQname],
                    name=paramQname, dependencies=", ".join((str(v) for v in undefinedVars)))
            if len(paramsCircularDep) > 0:
                val.modelXbrl.uuidError("235ac51c05744261bbb5a6db2185b59f",
                    modelObject=val.modelXbrl.qnameParameters[paramQname],
                    name=paramQname, dependencies=", ".join((str(d) for d in paramsCircularDep)) )
            
    for custFnSig in val.modelXbrl.modelCustomFunctionSignatures.values():
        custFnQname = custFnSig.qname
        if custFnQname.namespaceURI == "XbrlConst.xfi":
            val.modelXbrl.uuidError("edf7bb3336504dd2a76ea4da99514fe1",
                modelObject=custFnSig, name=custFnQname, namespace=custFnQname.namespaceURI )
        # any custom function implementations?
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.functionImplementation).fromModelObject(custFnSig):
            custFnImpl = modelRel.toModelObject
            custFnSig.customFunctionImplementation = custFnImpl
            if len(custFnImpl.inputNames) != len(custFnSig.inputTypes):
                val.modelXbrl.uuidError("1c25607ba1484d1ab3ce1348bed4673a",
                    modelObject=custFnSig, name=custFnQname, 
                    parameterCountSignature=len(custFnSig.inputTypes), parameterCountImplementation=len(custFnImpl.inputNames) )
        
    for custFnImpl in val.modelXbrl.modelCustomFunctionImplementations:
        if not val.modelXbrl.relationshipSet(XbrlConst.functionImplementation).toModelObject(custFnImpl):
            val.modelXbrl.uuidError("04fe2aed015b4e73a03b90b754602f44",
                modelObject=custFnSig, xlinkLabel=custFnImpl.xlinkLabel)
        custFnImpl.compile()
            
    # xpathContext is needed for filter setup for expressions such as aspect cover filter
    # determine parameter values
    xpathContext = XPathContext.create(val.modelXbrl)
    for paramQname in orderedParameters:
        modelParameter = val.modelXbrl.qnameParameters[paramQname]
        if not isinstance(modelParameter, ModelInstance):
            asType = modelParameter.asType
            asLocalName = asType.localName if asType else "string"
            try:
                if val.parameters and paramQname in val.parameters:
                    paramDataType, paramValue = val.parameters[paramQname]
                    typeLocalName = paramDataType.localName if paramDataType else "string"
                    value = FunctionXs.call(xpathContext, None, typeLocalName, [paramValue])
                    result = FunctionXs.call(xpathContext, None, asLocalName, [value])
                    if formulaOptions.traceParameterInputValue:
                        val.modelXbrl.uuidInfo("f65bc7b0a09e47ee8c0431baf4f6982b",
                            modelObject=modelParameter, name=paramQname, input=result)
                else:
                    result = modelParameter.evaluate(xpathContext, asType)
                    if formulaOptions.traceParameterExpressionResult:
                        val.modelXbrl.uuidInfo("66e090d3c1e3413e983a3ee124867fd3",
                            modelObject=modelParameter, name=paramQname, result=result)
                xpathContext.inScopeVars[paramQname] = result    # make visible to subsequent parameter expression 
            except XPathContext.XPathException as err:
                val.modelXbrl.error("xbrlve:parameterTypeMismatch" if err.code == "err:FORG0001" else err.code,
                    _("Parameter \n%(name)s \nException: \n%(error)s"), 
                    modelObject=modelParameter, name=paramQname, error=err.message)

    produceOutputXbrlInstance = False
    instanceProducingVariableSets = defaultdict(list)
        
    for modelVariableSet in val.modelXbrl.modelVariableSets:
        varSetInstanceDependencies = set()
        if isinstance(modelVariableSet, ModelFormula):
            instanceQname = None
            for modelRel in val.modelXbrl.relationshipSet(XbrlConst.formulaInstance).fromModelObject(modelVariableSet):
                instance = modelRel.toModelObject
                if isinstance(instance, ModelInstance):
                    if instanceQname is None:
                        instanceQname = instance.qname
                    else:
                        val.modelXbrl.uuidInfo("ae22dc6126534e64992a7ce1febf018f",
                            modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                            instanceTo=instanceQname, instanceTo2=instance.qname)
            if instanceQname is None: 
                instanceQname = XbrlConst.qnStandardOutputInstance
                instanceQnames.add(instanceQname)
            modelVariableSet.outputInstanceQname = instanceQname
            if val.validateSBRNL:
                val.modelXbrl.uuidError("4b5bf17cfaac4a71b24d72283b5f0735",
                    modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel)
        else:
            instanceQname = None
            modelVariableSet.countSatisfied = 0
            modelVariableSet.countNotSatisfied = 0
            checkValidationMessages(val, modelVariableSet)
        instanceProducingVariableSets[instanceQname].append(modelVariableSet)
        modelVariableSet.outputInstanceQname = instanceQname
        if modelVariableSet.aspectModel not in ("non-dimensional", "dimensional"):
            val.modelXbrl.uuidError("762bdf464fa74b418f839fb96ac38d22",
                modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, aspectModel=modelVariableSet.aspectModel)
        modelVariableSet.compile()
        modelVariableSet.hasConsistencyAssertion = False
            
        #determine dependencies within variable sets
        nameVariables = {}
        qnameRels = {}
        definedNamesSet = set()
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSet).fromModelObject(modelVariableSet):
            varqname = modelRel.variableQname
            if varqname:
                qnameRels[varqname] = modelRel
                toVariable = modelRel.toModelObject
                if varqname not in definedNamesSet:
                    definedNamesSet.add(varqname)
                if varqname not in nameVariables:
                    nameVariables[varqname] = toVariable
                elif nameVariables[varqname] != toVariable:
                    val.modelXbrl.uuidError("7ab3105609ce459585f232b8d70e4be3",
                        modelObject=toVariable, xlinkLabel=modelVariableSet.xlinkLabel, name=varqname )
                fromInstanceQnames = None
                for instRel in val.modelXbrl.relationshipSet(XbrlConst.instanceVariable).toModelObject(toVariable):
                    fromInstance = instRel.fromModelObject
                    if isinstance(fromInstance, ModelInstance):
                        fromInstanceQname = fromInstance.qname
                        varSetInstanceDependencies.add(fromInstanceQname)
                        instanceDependencies[instanceQname].add(fromInstanceQname)
                        if fromInstanceQnames is None: fromInstanceQnames = set()
                        fromInstanceQnames.add(fromInstanceQname)
                if fromInstanceQnames is None:
                    varSetInstanceDependencies.add(XbrlConst.qnStandardInputInstance)
                    if instanceQname: instanceDependencies[instanceQname].add(XbrlConst.qnStandardInputInstance)
                toVariable.fromInstanceQnames = fromInstanceQnames
            else:
                val.modelXbrl.uuidError("f2e320e094be4952960814c073c1a33e",
                    modelObject=modelRel, xlinkLabel=modelVariableSet.xlinkLabel, name=modelRel.variablename )
        checkVariablesScopeVisibleQnames(val, nameVariables, definedNamesSet, modelVariableSet)
        definedNamesSet |= parameterQnames
                
        variableDependencies = {}
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSet).fromModelObject(modelVariableSet):
            variable = modelRel.toModelObject
            if isinstance(variable, (ModelParameter,ModelVariable)):    # ignore anything not parameter or variable
                varqname = modelRel.variableQname
                depVars = variable.variableRefs()
                variableDependencies[varqname] = depVars
                if len(depVars) > 0 and formulaOptions.traceVariablesDependencies:
                    val.modelXbrl.uuidInfo("667d2cd7cae54b2ca7d15d29fbbb7bcd",
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                        name=varqname, dependencies=depVars)
                definedNamesSet.add(varqname)
                # check for fallback value variable references
                if isinstance(variable, ModelFactVariable):
                    for depVar in XPathParser.variableReferencesSet(variable.fallbackValueProg, variable):
                        if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                            val.modelXbrl.uuidError("06d2580ac4f349b9b4086ea4ba52c768",
                                modelObject=variable, xlinkLabel=modelVariableSet.xlinkLabel, 
                                fallbackValue=variable.fallbackValue, dependency=depVar)
                    # check for covering aspect not in variable set aspect model
                    checkFilterAspectModel(val, modelVariableSet, variable.filterRelationships, xpathContext)

        orderedNameSet = set()
        orderedNameList = []
        orderedAVariable = True
        while (orderedAVariable):
            orderedAVariable = False
            for varqname, depVars in variableDependencies.items():
                if varqname not in orderedNameSet and len(depVars - parameterQnames - orderedNameSet) == 0:
                    orderedNameList.append(varqname)
                    orderedNameSet.add(varqname)
                    orderedAVariable = True
                if varqname in instanceQnames:
                    varSetInstanceDependencies.add(varqname)
                    instanceDependencies[instanceQname].add(varqname)
                elif isinstance(nameVariables.get(varqname), ModelInstance):
                    instqname = nameVariables[varqname].qname
                    varSetInstanceDependencies.add(instqname)
                    instanceDependencies[instanceQname].add(instqname)
                    
        # anything unresolved?
        for varqname, depVars in variableDependencies.items():
            if varqname not in orderedNameSet:
                circularOrUndefVars = depVars - parameterQnames - orderedNameSet
                undefinedVars = circularOrUndefVars - definedNamesSet 
                varsCircularDep = circularOrUndefVars - undefinedVars
                if len(undefinedVars) > 0:
                    val.modelXbrl.uuidError("23d69ebe08ef47729d9c37da52d78a3f",
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                        nameFrom=varqname, nameTo=undefinedVars)
                if len(varsCircularDep) > 0:
                    val.modelXbrl.uuidError("29fba64a4fb94a25a0e5bba16534fe0a",
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, 
                        nameFrom=varqname, nameTo=varsCircularDep )
                    
        # check unresolved variable set dependencies
        for varSetDepVarQname in modelVariableSet.variableRefs():
            if varSetDepVarQname not in definedNamesSet and varSetDepVarQname not in parameterQnames:
                val.modelXbrl.uuidError("f867a5d438e546cfaa9633039f9a8ef1",
                    modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel,
                    name=varSetDepVarQname)
            if varSetDepVarQname in instanceQnames:
                varSetInstanceDependencies.add(varSetDepVarQname)
                instanceDependencies[instanceQname].add(varSetDepVarQname)
            elif isinstance(nameVariables.get(varSetDepVarQname), ModelInstance):
                instqname = nameVariables[varSetDepVarQname].qname
                varSetInstanceDependencies.add(instqname)
                instanceDependencies[instanceQname].add(instqname)
        
        if formulaOptions.traceVariablesOrder:
            val.modelXbrl.uuidInfo("e62ad8c921d54974b726c382c35c936f",
                   modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, dependencies=orderedNameList)
        
        if (formulaOptions.traceVariablesDependencies and len(varSetInstanceDependencies) > 0 and
            varSetInstanceDependencies != {XbrlConst.qnStandardInputInstance}):
            val.modelXbrl.uuidInfo("9e2998931fd34ff982fac8f8127d8655",
                   modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, dependencies=varSetInstanceDependencies)
            
        modelVariableSet.orderedVariableRelationships = []
        for varqname in orderedNameList:
            if varqname in qnameRels:
                modelVariableSet.orderedVariableRelationships.append(qnameRels[varqname])
                
        # check existence assertion variable dependencies
        if isinstance(modelVariableSet, ModelExistenceAssertion):
            for depVar in modelVariableSet.variableRefs():
                if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                    val.modelXbrl.uuidError("3dbe49792061490ea97a1a7a06248f51",
                        modelObject=modelVariableSet, xlinkLabel=modelVariableSet.xlinkLabel, name=depVar)
                    
        # check messages variable dependencies
        checkValidationMessageVariables(val, modelVariableSet, qnameRels)

        if isinstance(modelVariableSet, ModelFormula): # check consistency assertion message variables and its messages variables
            for consisAsserRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).toModelObject(modelVariableSet):
                consisAsser = consisAsserRel.fromModelObject
                if isinstance(consisAsser, ModelConsistencyAssertion):
                    checkValidationMessages(val, consisAsser)
                    checkValidationMessageVariables(val, consisAsser, qnameRels)
                        
        # check preconditions
        modelVariableSet.preconditions = []
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSetPrecondition).fromModelObject(modelVariableSet):
            precondition = modelRel.toModelObject
            if isinstance(precondition, ModelPrecondition):
                modelVariableSet.preconditions.append(precondition)
                
        # check typed dimension equality test
        val.modelXbrl.modelFormulaEqualityDefinitions = {}
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.equalityDefinition).modelRelationships:
            typedDomainElt = modelRel.fromModelObject
            modelEqualityDefinition = modelRel.toModelObject
            if typedDomainElt in val.modelXbrl.modelFormulaEqualityDefinitions:
                val.modelXbrl.uuidError("0c2b0744caff4692ac6fe59b744494d9",
                     modelObject=modelRel.arcElement, typedDomain=typedDomainElt.qname,
                     equalityDefinition1=modelEqualityDefinition.xlinkLabel,
                     equalityDefinition2=val.modelXbrl.modelFormulaEqualityDefinitions[typedDomainElt].xlinkLabel)
            else:
                modelEqualityDefinition.compile()
                val.modelXbrl.modelFormulaEqualityDefinitions[typedDomainElt] = modelEqualityDefinition
                
        # check for variable sets referencing fact or general variables
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSetFilter).fromModelObject(modelVariableSet):
            varSetFilter = modelRel.toModelObject
            if modelRel.isCovered:
                val.modelXbrl.uuidWarning("2024645cea0449c4be00bdd0e17c0be6",
                     modelObject=varSetFilter, xlinkLabel=modelVariableSet.xlinkLabel, filterLabel=varSetFilter.xlinkLabel)
                modelRel._isCovered = False # block group filter from being able to covere
            for depVar in varSetFilter.variableRefs():
                if depVar in qnameRels and isinstance(qnameRels[depVar].toModelObject,ModelVariable):
                    val.modelXbrl.uuidError("b8cf19645d224a18b67ac05e2ef74016",
                        modelObject=varSetFilter, xlinkLabel=modelVariableSet.xlinkLabel, filterLabel=varSetFilter.xlinkLabel, name=depVar)
                    
        # check aspects of formula
        if isinstance(modelVariableSet, ModelFormula):
            checkFormulaRules(val, modelVariableSet, nameVariables)
            
    # determine instance dependency order
    orderedInstancesSet = set()
    stdInpInst = {XbrlConst.qnStandardInputInstance}
    orderedInstancesList = []
    orderedAnInstance = True
    while (orderedAnInstance):
        orderedAnInstance = False
        for instqname, depInsts in instanceDependencies.items():
            if instqname and instqname not in orderedInstancesSet and len(depInsts - stdInpInst - orderedInstancesSet) == 0:
                orderedInstancesList.append(instqname)
                orderedInstancesSet.add(instqname)
                orderedAnInstance = True
    # add instances with variable sets with no variables or other dependencies
    for independentInstance in instanceProducingVariableSets.keys() - orderedInstancesList:
        orderedInstancesList.append(independentInstance)
        orderedInstancesSet.add(independentInstance)
    if None not in orderedInstancesList:
        orderedInstancesList.append(None)  # assertions come after all formulas that produce outputs

    # anything unresolved?
    for instqname, depInsts in instanceDependencies.items():
        if instqname not in orderedInstancesSet:
            # can also be satisfied from an input DTS
            missingDependentInstances = depInsts - stdInpInst
            if val.parameters: missingDependentInstances -= val.parameters.keys() 
            if instqname:
                if missingDependentInstances:
                    val.modelXbrl.uuidError("ea6d76f4558e415fb460f022573f43dd",
                        modelObject=val.modelXbrl,
                        name=instqname, dependencies=missingDependentInstances )
                elif instqname == XbrlConst.qnStandardOutputInstance:
                    orderedInstancesSet.add(instqname)
                    orderedInstancesList.append(instqname) # standard output formula, all input dependencies in parameters
            ''' future check?  if instance has no external input or producing formula
            else:
                val.modelXbrl.error("xbrlvarinste:instanceVariableRecursionCycle",
                    _("Unresolved dependencies of an assertion's variables on instances %(dependencies)s"),
                    dependencies=str(depInsts - stdInpInst) )
            '''

    if formulaOptions.traceVariablesOrder and len(orderedInstancesList) > 1:
        val.modelXbrl.uuidInfo("e559b9e9d4d348d684ffb892104ff6bf",
                modelObject=val.modelXbrl, dependencies=orderedInstancesList)

    # linked consistency assertions
    for modelRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).modelRelationships:
        if (modelRel.fromModelObject is not None and modelRel.toModelObject is not None and 
            isinstance(modelRel.toModelObject,ModelFormula)):
            consisAsser = modelRel.fromModelObject
            consisAsser.countSatisfied = 0
            consisAsser.countNotSatisfied = 0
            if consisAsser.hasProportionalAcceptanceRadius and consisAsser.hasAbsoluteAcceptanceRadius:
                val.modelXbrl.uuidError("07190b2392354186bcba095db2b74fda",
                    modelObject=consisAsser, xlinkLabel=consisAsser.xlinkLabel)
            consisAsser.orderedVariableRelationships = []
            for consisParamRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionParameter).fromModelObject(consisAsser):
                if isinstance(consisParamRel.toModelObject, ModelVariable):
                    val.modelXbrl.uuidError("c06c435715c949f0a24c766ecccc709d",
                        modelObject=consisAsser, xlinkLabel=consisAsser.xlinkLabel, 
                        elementTo=consisParamRel.toModelObject.localName, xlinkLabelTo=consisParamRel.toModelObject.xlinkLabel)
                else:
                    consisAsser.orderedVariableRelationships.append(consisParamRel)
            consisAsser.compile()
            modelRel.toModelObject.hasConsistencyAssertion = True

    # validate default dimensions in instances and accumulate multi-instance-default dimension aspects
    xpathContext.defaultDimensionAspects = set(val.modelXbrl.qnameDimensionDefaults.keys())
    for instanceQname in instanceQnames:
        if (instanceQname not in (XbrlConst.qnStandardInputInstance,XbrlConst.qnStandardOutputInstance) and
            val.parameters and instanceQname in val.parameters):
            namedInstance = val.parameters[instanceQname][1][0]
            ValidateXbrlDimensions.loadDimensionDefaults(namedInstance)
            xpathContext.defaultDimensionAspects |= namedInstance.qnameDimensionDefaults.keys()

    # check for variable set dependencies across output instances produced
    for instanceQname, modelVariableSets in instanceProducingVariableSets.items():
        for modelVariableSet in modelVariableSets:
            for varScopeRel in val.modelXbrl.relationshipSet(XbrlConst.variablesScope).toModelObject(modelVariableSet):
                if varScopeRel.fromModelObject is not None:
                    sourceVariableSet = varScopeRel.fromModelObject
                    if sourceVariableSet.outputInstanceQname != instanceQname:
                        val.modelXbrl.uuidError("d8b160feb3f449669fbae00a0a1c2cc4",
                            modelObject=modelVariableSet, 
                            xlinkLabel1=sourceVariableSet.xlinkLabel, instance1=sourceVariableSet.outputInstanceQname,
                            xlinkLabel2=modelVariableSet.xlinkLabel, instance2=modelVariableSet.outputInstanceQname)
                    if sourceVariableSet.aspectModel != modelVariableSet.aspectModel:
                        val.modelXbrl.uuidError("81ccdcf325f44d59b4d9c4caa5a47180",
                            modelObject=modelVariableSet, 
                            xlinkLabel1=sourceVariableSet.xlinkLabel, aspectModel1=sourceVariableSet.aspectModel,
                            xlinkLabel2=modelVariableSet.xlinkLabel, aspectModel2=modelVariableSet.aspectModel)

    if initialErrorCount < val.modelXbrl.logCountErr:
        return  # don't try to execute
        

    # formula output instances    
    if instanceQnames:      
        schemaRefs = [val.modelXbrl.modelDocument.relativeUri(referencedDoc.uri)
                        for referencedDoc in val.modelXbrl.modelDocument.referencesDocument.keys()
                            if referencedDoc.type == ModelDocument.Type.SCHEMA]
        
    outputXbrlInstance = None
    for instanceQname in instanceQnames:
        if instanceQname == XbrlConst.qnStandardInputInstance:
            continue    # always present the standard way
        if val.parameters and instanceQname in val.parameters:
            namedInstance = val.parameters[instanceQname][1]
        else:   # empty intermediate instance 
            uri = val.modelXbrl.modelDocument.filepath[:-4] + "-output-XBRL-instance"
            if instanceQname != XbrlConst.qnStandardOutputInstance:
                uri = uri + "-" + instanceQname.localName
            uri = uri + ".xml"
            namedInstance = ModelXbrl.create(val.modelXbrl.modelManager, 
                                             newDocumentType=ModelDocument.Type.INSTANCE,
                                             url=uri,
                                             schemaRefs=schemaRefs,
                                             isEntry=True)
            ValidateXbrlDimensions.loadDimensionDefaults(namedInstance) # need dimension defaults 
        xpathContext.inScopeVars[instanceQname] = namedInstance
        if instanceQname == XbrlConst.qnStandardOutputInstance:
            outputXbrlInstance = namedInstance
        
    # evaluate consistency assertions
    
    # evaluate variable sets not in consistency assertions
    for instanceQname in orderedInstancesList:
        for modelVariableSet in instanceProducingVariableSets[instanceQname]:
            # produce variable evaluations if no dependent variables-scope relationships
            if not val.modelXbrl.relationshipSet(XbrlConst.variablesScope).toModelObject(modelVariableSet):
                from arelle.FormulaEvaluator import evaluate
                try:
                    evaluate(xpathContext, modelVariableSet)
                except XPathContext.XPathException as err:
                    val.modelXbrl.error(err.code,
                        _("Variable set \n%(variableSet)s \nException: \n%(error)s"), 
                        modelObject=modelVariableSet, variableSet=str(modelVariableSet), error=err.message)
            
    # log assertion result counts
    asserTests = {}
    for exisValAsser in val.modelXbrl.modelVariableSets:
        if isinstance(exisValAsser, ModelVariableSetAssertion):
            asserTests[exisValAsser.id] = (exisValAsser.countSatisfied, exisValAsser.countNotSatisfied)
            if formulaOptions.traceAssertionResultCounts:
                val.modelXbrl.uuidInfo("2acce4bd0844490ca73f690b16756beb",
                    modelObject=exisValAsser,
                    assertionType="Existence" if isinstance(exisValAsser, ModelExistenceAssertion) else "Value", 
                    id=exisValAsser.id, satisfiedCount=exisValAsser.countSatisfied, notSatisfiedCount=exisValAsser.countNotSatisfied)

    for modelRel in val.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).modelRelationships:
        if modelRel.fromModelObject is not None and modelRel.toModelObject is not None and \
           isinstance(modelRel.toModelObject,ModelFormula):
            consisAsser = modelRel.fromModelObject
            asserTests[consisAsser.id] = (consisAsser.countSatisfied, consisAsser.countNotSatisfied)
            if formulaOptions.traceAssertionResultCounts:
                val.modelXbrl.uuidInfo("1df1a57a3d9342a2be649915bf906fa5",
                    modelObject=consisAsser, id=consisAsser.id, 
                    satisfiedCount=consisAsser.countSatisfied, notSatisfiedCount=consisAsser.countNotSatisfied)
            
    if asserTests: # pass assertion results to validation if appropriate
        val.modelXbrl.info("asrtNoLog", None, assertionResults=asserTests);

    # display output instance
    if outputXbrlInstance:
        if val.modelXbrl.formulaOutputInstance:
            # close prior instance, usually closed by caller to validate as it may affect UI on different thread
            val.modelXbrl.formulaOutputInstance.close()
        val.modelXbrl.formulaOutputInstance = outputXbrlInstance

def checkVariablesScopeVisibleQnames(val, nameVariables, definedNamesSet, modelVariableSet):
    for visibleVarSetRel in val.modelXbrl.relationshipSet(XbrlConst.variablesScope).toModelObject(modelVariableSet):
        varqname = visibleVarSetRel.variableQname # name (if any) of the formula result
        if varqname:
            if varqname not in nameVariables:
                nameVariables[varqname] = visibleVarSetRel.fromModelObject
            if varqname not in definedNamesSet:
                definedNamesSet.add(varqname)
        visibleVarSet = visibleVarSetRel.fromModelObject
        for modelRel in val.modelXbrl.relationshipSet(XbrlConst.variableSet).fromModelObject(visibleVarSet):
            varqname = modelRel.variableQname
            if varqname:
                if varqname not in nameVariables:
                    nameVariables[varqname] = modelRel.toModelObject
                if varqname not in definedNamesSet:
                    definedNamesSet.add(varqname)
        checkVariablesScopeVisibleQnames(val, nameVariables, definedNamesSet, visibleVarSet)

def checkFilterAspectModel(val, variableSet, filterRelationships, xpathContext, uncoverableAspects=None):
    if uncoverableAspects is None:
        oppositeAspectModel = ({'dimensional','non-dimensional'} - {variableSet.aspectModel}).pop()
        try:
            uncoverableAspects = aspectModels[oppositeAspectModel] - aspectModels[variableSet.aspectModel]
        except KeyError:    # bad aspect model, not an issue for this test
            return
    acfAspectsCovering = {}
    for varFilterRel in filterRelationships:
        filter = varFilterRel.toModelObject
        isAllAspectCoverFilter = False
        if isinstance(filter, ModelAspectCover):
            for aspect in filter.aspectsCovered(None, xpathContext):
                if aspect in acfAspectsCovering:
                    otherFilterCover, otherFilterLabel = acfAspectsCovering[aspect]
                    if otherFilterCover != varFilterRel.isCovered:
                        val.modelXbrl.uuidError("c550ec846a81454fa6b1ec9d3bd41a17",
                            modelObject=variableSet, xlinkLabel=variableSet.xlinkLabel, filterLabel=filter.xlinkLabel, 
                            aspect=str(aspect) if isinstance(aspect,QName) else Aspect.label[aspect],
                            filterLabel2=otherFilterLabel)
                else:
                    acfAspectsCovering[aspect] = (varFilterRel.isCovered, filter.xlinkLabel)
            isAllAspectCoverFilter = filter.isAll
        if True: # changed for test case 50210 v03 varFilterRel.isCovered:
            try:
                aspectsCovered = filter.aspectsCovered(None)
                if (not isAllAspectCoverFilter and 
                    (any(isinstance(aspect,QName) for aspect in aspectsCovered) and Aspect.DIMENSIONS in uncoverableAspects
                     or (aspectsCovered & uncoverableAspects))):
                    val.modelXbrl.uuidError("6fcf47730be94afba2bcaa74cbbeebc4",
                        modelObject=variableSet, xlinkLabel=variableSet.xlinkLabel, aspectModel=variableSet.aspectModel, 
                        filterName=filter.localName, filterLabel=filter.xlinkLabel)
            except Exception:
                pass
            if hasattr(filter, "filterRelationships"): # check and & or filters
                checkFilterAspectModel(val, variableSet, filter.filterRelationships, xpathContext, uncoverableAspects)
        
def checkFormulaRules(val, formula, nameVariables):
    if not (formula.hasRule(Aspect.CONCEPT) or formula.source(Aspect.CONCEPT)):
        if XmlUtil.hasDescendant(formula, XbrlConst.formula, "concept"):
            val.modelXbrl.uuidError("fb060c3155ea4a03a6f7ccd5bfd3e9cc",
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
        else:
            val.modelXbrl.uuidError("8cbc17c65c28482d9aa843aff84351c0",
                modelObject=formula, xlinkLabel=formula.xlinkLabel)
    if not isinstance(formula, ModelTuple):
        if (not (formula.hasRule(Aspect.SCHEME) or formula.source(Aspect.SCHEME)) or
            not (formula.hasRule(Aspect.VALUE) or formula.source(Aspect.VALUE))):
            if XmlUtil.hasDescendant(formula, XbrlConst.formula, "entityIdentifier"):
                val.modelXbrl.uuidError("0b473dbc42fd48b5b79fa16df16c92df",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel)
            else:
                val.modelXbrl.uuidError("a0683918f6e5451b8531d7766ab8c067",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel)
        if not (formula.hasRule(Aspect.PERIOD_TYPE) or formula.source(Aspect.PERIOD_TYPE)):
            if XmlUtil.hasDescendant(formula, XbrlConst.formula, "period"):
                val.modelXbrl.uuidError("7133b9aeaa454515bda80b0e6daa0a9d",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel)
            else:
                val.modelXbrl.uuidError("5ee63ee7786a4da8a4757d8405ced4d2",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel)
        # for unit need to see if the qname is statically determinable to determine if numeric
        concept = val.modelXbrl.qnameConcepts.get(formula.evaluateRule(None, Aspect.CONCEPT))
        if concept is None: # is there a source with a static QName filter
            sourceFactVar = nameVariables.get(formula.source(Aspect.CONCEPT))
            if isinstance(sourceFactVar, ModelFactVariable):
                for varFilterRels in (formula.groupFilterRelationships, sourceFactVar.filterRelationships):
                    for varFilterRel in varFilterRels:
                        filter = varFilterRel.toModelObject
                        if isinstance(filter,ModelConceptName):  # relationship not constrained to real filters
                            for conceptQname in filter.conceptQnames:
                                concept = val.modelXbrl.qnameConcepts.get(conceptQname)
                                if concept is not None and concept.isNumeric:
                                    break
        if concept is not None: # from concept aspect rule or from source factVariable concept Qname filter
            if concept.isNumeric:
                if not (formula.hasRule(Aspect.MULTIPLY_BY) or formula.hasRule(Aspect.DIVIDE_BY) or formula.source(Aspect.UNIT)):
                    if XmlUtil.hasDescendant(formula, XbrlConst.formula, "unit"):
                        val.modelXbrl.uuidError("038f819691474c13b3a9df0887aa4431",
                            modelObject=formula, xlinkLabel=formula.xlinkLabel)
                    else:
                        val.modelXbrl.uuidError("33b64f2630ec4694aa715dabdec14ab7",
                            modelObject=formula, xlinkLabel=formula.xlinkLabel)
            elif (formula.hasRule(Aspect.MULTIPLY_BY) or formula.hasRule(Aspect.DIVIDE_BY) or 
                  formula.source(Aspect.UNIT, acceptFormulaSource=False)):
                val.modelXbrl.uuidError("f1556f588cf14c7db37c3e170ee3f03f",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, concept=concept.qname)
            aspectPeriodType = formula.evaluateRule(None, Aspect.PERIOD_TYPE)
            if ((concept.periodType == "duration" and aspectPeriodType == "instant") or
                (concept.periodType == "instant" and aspectPeriodType in ("duration","forever"))):
                val.modelXbrl.uuidError("503699c0f1944192bd2f9d948502687d",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, concept=concept.qname, aspectPeriodType=aspectPeriodType, conceptPeriodType=concept.periodType)
        
        # check dimension elements
        for eltName, dim, badUsageUuid, missingSavUuid in (("explicitDimension", "explicit", "f5e14f9112764d7e9fafc5fcc138e476", "53eb7367247a42fca29419b0da0139ed"),
                                                         ("typedDimension", "typed", "065c3f67cb6240cda3da5696add2b6db", "c978f58dfca3455d9c158ca59e5d956d")):
            for dimElt in XmlUtil.descendants(formula, XbrlConst.formula, eltName):
                dimQname = qname(dimElt, dimElt.get("dimension"))
                dimConcept = val.modelXbrl.qnameConcepts.get(dimQname)
                if dimQname and (dimConcept is None or (not dimConcept.isExplicitDimension if dim == "explicit" else not dimConcept.isTypedDimension)):
                    val.modelXbrl.uuidError(badUsageUuid,
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, dimensionType=dim, dimension=dimQname)
                elif not XmlUtil.hasChild(dimElt, XbrlConst.formula, "*") and not formula.source(Aspect.DIMENSIONS, dimElt):
                    val.modelXbrl.uuidError(missingSavUuid,
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, dimensionType=dim, dimension=dimQname)
        
        # check aspect model expectations
        if formula.aspectModel == "non-dimensional":
            unexpectedElts = XmlUtil.descendants(formula, XbrlConst.formula, ("explicitDimension", "typedDimension"))
            if unexpectedElts:
                val.modelXbrl.uuidError("dc637b17b86f422682f388a7a0b9ab05",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, aspectModel=formula.aspectModel, undefinedAspects=", ".join([elt.localName for elt in unexpectedElts]))

    # check source qnames
    for sourceElt in ([formula] + 
                     XmlUtil.descendants(formula, XbrlConst.formula, "*", "source","*")):
        if sourceElt.get("source") is not None:
            qnSource = qname(sourceElt, sourceElt.get("source"), noPrefixIsNoNamespace=True)
            if qnSource == XbrlConst.qnFormulaUncovered:
                if formula.implicitFiltering != "true":
                    val.modelXbrl.uuidError("30a9f143c3824ef69e6ac2b998bf13aa",
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=sourceElt.localName) 
            elif qnSource not in nameVariables:
                val.modelXbrl.uuidError("18ec638893fa45fa8c5f84b5a54c77bd",
                    modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource)
            else:
                factVariable = nameVariables.get(qnSource)
                if isinstance(factVariable, ModelVariableSet):
                    pass
                elif not isinstance(factVariable, ModelFactVariable):
                    val.modelXbrl.uuidError("fc83540263304df0a4353b2374061cb9",
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource, element=factVariable.localName)
                elif factVariable.fallbackValue is not None:
                    val.modelXbrl.uuidError("4efd975f53424722ac0cac609008bffe",
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource)
                elif sourceElt.localName == "formula" and factVariable.bindAsSequence == "true":
                    val.modelXbrl.uuidError("995e3f8fd0b0470bbc70e71f2aad9136",
                        modelObject=formula, xlinkLabel=formula.xlinkLabel, name=qnSource)
                
def checkValidationMessages(val, modelVariableSet):
    for msgRelationship in (XbrlConst.assertionSatisfiedMessage, XbrlConst.assertionUnsatisfiedMessage):
        for modelRel in val.modelXbrl.relationshipSet(msgRelationship).fromModelObject(modelVariableSet):
            message = modelRel.toModelObject
            if not hasattr(message,"expressions"):
                formatString = []
                expressions = []
                bracketNesting = 0
                skipTo = None
                expressionIndex = 0
                expression = None
                lastC = None
                for c in message.text:
                    if skipTo:
                        if c == skipTo:
                            skipTo = None
                    if expression is not None and c in ('\'', '"'):
                        skipTo = c
                    elif lastC == c and c in ('{','}'):
                        lastC = None
                    elif lastC == '{': 
                        bracketNesting += 1
                        expression = []
                        lastC = None
                    elif c == '}' and expression is not None: 
                        expressions.append( ''.join(expression).strip() )
                        expression = None
                        formatString.append( "0[{0}]".format(expressionIndex) )
                        expressionIndex += 1
                        lastC = c
                    elif lastC == '}':
                        bracketNesting -= 1
                        lastC = None
                    else:
                        lastC = c
                        
                    if expression is not None: expression.append(c)
                    else: formatString.append(c)
                    
                if lastC == '}':
                    bracketNesting -= 1
                if bracketNesting:
                    val.modelXbrl.uuidError("6d0d7613c74a43718129f64bc28c4869" if bracketNesting < 0 else "b280adf9b6104bf7b1160650a5edbba5",
                        modelObject=message, xlinkLabel=message.xlinkLabel, 
                        character='{' if bracketNesting < 0 else '}', 
                        text=message.text)
                else:
                    message.expressions = expressions
                    message.formatString = ''.join( formatString )

def checkValidationMessageVariables(val, modelVariableSet, varNames):
    if isinstance(modelVariableSet, ModelConsistencyAssertion):
        varSetVars = (qname(XbrlConst.ca,'aspect-matched-facts'),
                      qname(XbrlConst.ca,'acceptance-radius'),
                      qname(XbrlConst.ca,'absolute-acceptance-radius-expression'),
                      qname(XbrlConst.ca,'proportional-acceptance-radius-expression'))
    elif isinstance(modelVariableSet, ModelExistenceAssertion):
        varSetVars = (qname(XbrlConst.ea,'text-expression'),)
    elif isinstance(modelVariableSet, ModelValueAssertion):
        varSetVars = (qname(XbrlConst.va,'text-expression'),)
    for msgRelationship in (XbrlConst.assertionSatisfiedMessage, XbrlConst.assertionUnsatisfiedMessage):
        for modelRel in val.modelXbrl.relationshipSet(msgRelationship).fromModelObject(modelVariableSet):
            message = modelRel.toModelObject
            message.compile()
            for msgVarQname in message.variableRefs():
                if msgVarQname not in varNames and msgVarQname not in varSetVars:
                    val.modelXbrl.uuidError("7954ed9453c8486f9e546cbbc7da6f9e",
                        modelObject=message, xlinkLabel=message.xlinkLabel, name=msgVarQname)
