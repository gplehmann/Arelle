'''
Created on Jan 9, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from arelle import XbrlConst
from arelle.XbrlUtil import xEqual, S_EQUAL2
from arelle.ValidateXbrlCalcs import inferredPrecision, roundValue
from math import fabs

def evaluate(xpCtx, varSet, derivedFact):
    # there may be multiple consis assertions parenting any formula
    for consisAsserRel in xpCtx.modelXbrl.relationshipSet(XbrlConst.consistencyAssertionFormula).toModelObject(varSet):
        consisAsser = consisAsserRel.fromModelObject
        hasProportionalAcceptanceRadius = consisAsser.hasProportionalAcceptanceRadius
        hasAbsoluteAcceptanceRadius = consisAsser.hasAbsoluteAcceptanceRadius
        if derivedFact is None:
            continue
        isNumeric = derivedFact.isNumeric
        if isNumeric and not derivedFact.isNil:
            derivedFactInferredPrecision = inferredPrecision(derivedFact)
            if derivedFactInferredPrecision == 0 and not hasProportionalAcceptanceRadius and not hasAbsoluteAcceptanceRadius:
                if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                    xpCtx.modelXbrl.uuidInfo("b454faa89eb04ca1a03378c63c0a7a22",
                         modelObject=consisAsser, id=consisAsser.id, xlinkLabel=varSet.xlinkLabel, derivedFact=derivedFact)
                continue
    
        # check xbrl validity of new fact
        
        # find source facts which match derived fact
        aspectMatchedInputFacts = []
        isStrict = consisAsser.isStrict
        for inputFact in xpCtx.modelXbrl.facts:
            if (not inputFact.isNil and
                inputFact.qname == derivedFact.qname and
                inputFact.context.isEqualTo(derivedFact.context,
                                            dimensionalAspectModel=(varSet.aspectModel == "dimensional")) and
                (not isNumeric or inputFact.unit.isEqualTo(derivedFact.unit))):
                aspectMatchedInputFacts.append( inputFact )
        
        if len(aspectMatchedInputFacts) == 0:
            if isStrict:
                if derivedFact.isNil:
                    isSatisfied = True
                else:
                    isSatisfied = False
            else:
                if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                    xpCtx.modelXbrl.uuidInfo("40e5ae47344a44219577c759898a76f2",
                         modelObject=consisAsser, id=consisAsser.id, xlinkLabel=varSet.xlinkLabel, derivedFact=derivedFact)
                continue
        elif derivedFact.isNil:
            isSatisfied = False
        else:
            isSatisfied = True
                
        paramQnamesAdded = []
        for paramRel in consisAsser.orderedVariableRelationships:
            paramQname = paramRel.variableQname
            paramVar = paramRel.toModelObject
            paramValue = xpCtx.inScopeVars.get(paramVar.qname)
            paramAlreadyInVars = paramQname in xpCtx.inScopeVars
            if not paramAlreadyInVars:
                paramQnamesAdded.append(paramQname)
                xpCtx.inScopeVars[paramQname] = paramValue
        for fact in aspectMatchedInputFacts:
            if isSatisfied != True: 
                break
            if fact.isNil:
                if not derivedFact.isNil:
                    isSatisfied = False
            elif isNumeric:
                factInferredPrecision = inferredPrecision(fact)
                if factInferredPrecision == 0 and not hasProportionalAcceptanceRadius and not hasAbsoluteAcceptanceRadius:
                    if xpCtx.formulaOptions.traceVariableSetExpressionResult:
                        xpCtx.modelXbrl.uuidInfo("ac24c65f7b6b4ecf80f46efa10a9a237",
                             modelObject=consisAsser, id=consisAsser.id, xlinkLabel=varSet.xlinkLabel, derivedFact=derivedFact)
                        isSatisfied = None
                        break
                if hasProportionalAcceptanceRadius or hasAbsoluteAcceptanceRadius:
                    acceptance = consisAsser.evalRadius(xpCtx, derivedFact.vEqValue)
                    if acceptance is not None:
                        if hasProportionalAcceptanceRadius:
                            acceptance *= derivedFact.vEqValue
                        isSatisfied = fabs(derivedFact.vEqValue - fact.vEqValue) <= fabs(acceptance)
                    else:
                        isSatisfied = None  # no radius
                else:
                    p = min(derivedFactInferredPrecision, factInferredPrecision)
                    if (p == 0 or
                        roundValue(derivedFact.vEqValue, precision=p) != roundValue(fact.vEqValue, precision=p)):
                        isSatisfied = False
            else:
                if not xEqual(fact, derivedFact, equalMode=S_EQUAL2):
                    isSatisfied = False
        for paramQname in paramQnamesAdded:
            xpCtx.inScopeVars.pop(paramQname)
        if isSatisfied is None:
            continue    # no evaluation
        if xpCtx.formulaOptions.traceVariableSetExpressionResult:
            xpCtx.modelXbrl.uuidInfo("05f0c23b60ae43259f3ddc6db7473cdd",
                 modelObject=consisAsser, id=consisAsser.id, result=isSatisfied)
        message = consisAsser.message(isSatisfied)
        if message is not None:
            xpCtx.modelXbrl.info("message:" + consisAsser.id, message.evaluate(xpCtx),
                                 modelObject=message)
        if isSatisfied: consisAsser.countSatisfied += 1
        else: consisAsser.countNotSatisfied += 1
