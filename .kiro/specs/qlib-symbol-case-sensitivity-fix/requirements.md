# Requirements Document

## Introduction

The QLib integration layer currently has a critical issue with symbol generation and lookup that affects the reliability of data export and retrieval. Cryptocurrency addresses are case-sensitive, but the current implementation loses case information during symbol processing, breaking reverse lookups and data integrity. This feature addresses the case-sensitivity issue to ensure reliable symbol-to-pool mapping in the QLib integration.

## Requirements

### Requirement 1

**User Story:** As a QLib data consumer, I want symbol names to maintain case-sensitive cryptocurrency addresses, so that I can reliably map symbols back to their original pool addresses.

#### Acceptance Criteria

1. WHEN a pool with mixed-case address is processed THEN the generated symbol SHALL preserve the original case exactly
2. WHEN a symbol is used for reverse lookup THEN the system SHALL correctly identify the original pool regardless of case variations in the lookup
3. WHEN symbols are exported to QLib format THEN the case-sensitive addresses SHALL be maintained in the symbol field
4. WHEN the system processes symbols that have been converted to lowercase by external systems THEN it SHALL still correctly map them back to the original pools

### Requirement 2

**User Story:** As a system administrator, I want the QLib exporter to handle case-insensitive symbol lookups gracefully, so that the system remains robust when interfacing with external tools that normalize case.

#### Acceptance Criteria

1. WHEN a lowercase symbol is provided for lookup THEN the system SHALL find the corresponding pool using case-insensitive matching
2. WHEN multiple pools could match a case-insensitive lookup THEN the system SHALL return the exact case match if available, otherwise the first match
3. WHEN symbol validation is performed THEN the system SHALL accept both original case and lowercase versions as valid
4. WHEN exporting data THEN the system SHALL maintain a bidirectional mapping between case-sensitive and case-insensitive symbol representations

### Requirement 3

**User Story:** As a developer integrating with the QLib exporter, I want clear documentation and methods for handling case-sensitive symbols, so that I can build reliable applications on top of the data export functionality.

#### Acceptance Criteria

1. WHEN using the QLib exporter API THEN there SHALL be methods that accept both case-sensitive and case-insensitive symbol inputs
2. WHEN symbol lookup fails THEN the system SHALL provide clear error messages indicating whether the issue is case-sensitivity related
3. WHEN exporting symbol lists THEN the system SHALL provide metadata about case-sensitivity requirements
4. WHEN performing bulk operations THEN the system SHALL handle mixed-case symbol lists efficiently without performance degradation