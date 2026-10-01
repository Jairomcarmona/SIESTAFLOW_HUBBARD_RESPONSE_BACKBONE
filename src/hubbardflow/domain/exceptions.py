class HubbardFlowError(Exception):
    pass

class CardinalConstraintViolation(HubbardFlowError): pass
class AggregationShapeViolation(HubbardFlowError): pass
class SemanticValidationFailure(HubbardFlowError): pass
class MethodologyLockMismatch(HubbardFlowError): pass
class AntisymmetryGateFailure(HubbardFlowError): pass
class SingularMatrixError(HubbardFlowError): pass
class IllConditionedMatrixError(HubbardFlowError): pass
class InversionResidualFailure(HubbardFlowError): pass
class UnitsViolation(HubbardFlowError): pass
class ReferenceDMMismatch(HubbardFlowError): pass
class BareContractUnresolved(HubbardFlowError): pass
class SelectionPolicyNotLocked(HubbardFlowError): pass
class ReductionJustificationRequired(HubbardFlowError): pass
class AlphaGridValidationError(HubbardFlowError): pass
class RecordCompletenessError(HubbardFlowError): pass
class BijectionViolation(HubbardFlowError): pass
class LstsqZoneViolation(HubbardFlowError): pass
class SiestaParserError(HubbardFlowError): pass
class ChecksumFailure(SiestaParserError): pass
class ExecutionError(HubbardFlowError): pass
