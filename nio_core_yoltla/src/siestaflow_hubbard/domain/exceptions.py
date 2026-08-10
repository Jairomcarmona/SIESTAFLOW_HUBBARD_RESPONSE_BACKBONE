class SiestaflowError(Exception):
    pass

class CardinalConstraintViolation(SiestaflowError): pass
class AggregationShapeViolation(SiestaflowError): pass
class SemanticValidationFailure(SiestaflowError): pass
class MethodologyLockMismatch(SiestaflowError): pass
class AntisymmetryGateFailure(SiestaflowError): pass
class SingularMatrixError(SiestaflowError): pass
class IllConditionedMatrixError(SiestaflowError): pass
class InversionResidualFailure(SiestaflowError): pass
class UnitsViolation(SiestaflowError): pass
class ReferenceDMMismatch(SiestaflowError): pass
class BareContractUnresolved(SiestaflowError): pass
class SelectionPolicyNotLocked(SiestaflowError): pass
class ReductionJustificationRequired(SiestaflowError): pass
class AlphaGridValidationError(SiestaflowError): pass
class RecordCompletenessError(SiestaflowError): pass
class BijectionViolation(SiestaflowError): pass
class LstsqZoneViolation(SiestaflowError): pass
class SiestaParserError(SiestaflowError): pass
class ChecksumFailure(SiestaParserError): pass
class ExecutionError(SiestaflowError): pass
