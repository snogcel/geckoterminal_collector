# Design Document

## Overview

This design addresses two critical issues in the new pools collection system:

1. **Data Validation Failures**: The new pools collector is failing to validate API responses due to missing 'attributes' fields, suggesting either API response format changes or parsing issues.

2. **Rate Limiting Async/Await Error**: The CLI code is incorrectly trying to `await` the `get_status()` method of the rate limiter, which returns a dictionary, not a coroutine.

The solution involves enhancing data validation resilience, improving error reporting, and fixing the async/await usage in rate limiting status retrieval.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    New Pools Collection System                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   API Response  │  │  Data Validator │  │ Rate Limiter    │  │
│  │   Analyzer      │  │   Enhanced      │  │ Status Handler  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│           │                     │                     │          │
│           ▼                     ▼                     ▼          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Response Format │  │ Fallback Data   │  │ Sync Status     │  │
│  │ Detection       │  │ Extraction      │  │ Retrieval       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **API Response Analysis**: Analyze incoming API responses to detect format variations
2. **Enhanced Validation**: Implement multi-strategy validation with detailed error reporting
3. **Fallback Extraction**: Use alternative field mappings when primary extraction fails
4. **Rate Limiting Fix**: Remove incorrect `await` usage for synchronous status methods

## Components and Interfaces

### 1. Enhanced Response Analyzer

**Purpose**: Analyze API response structure and detect format variations

**Interface**:
```python
class ResponseAnalyzer:
    @staticmethod
    def analyze_structure(data: Any) -> ResponseStructureInfo
    
    @staticmethod
    def detect_format_type(data: Any) -> ResponseFormatType
    
    @staticmethod
    def log_structure_details(data: Any, logger: Logger) -> None
```

**Key Methods**:
- `analyze_structure()`: Examine response structure and identify available fields
- `detect_format_type()`: Determine if response is standard, nested, or alternative format
- `log_structure_details()`: Provide detailed logging of response structure for debugging

### 2. Enhanced Data Validator

**Purpose**: Provide resilient validation with multiple parsing strategies

**Interface**:
```python
class EnhancedNewPoolsValidator:
    def validate_with_fallback(self, data: List[Dict]) -> ValidationResult
    
    def extract_pool_info_resilient(self, pool_data: Dict) -> Optional[Dict]
    
    def try_alternative_mappings(self, pool_data: Dict) -> Optional[Dict]
```

**Key Methods**:
- `validate_with_fallback()`: Validate data with multiple strategies
- `extract_pool_info_resilient()`: Extract pool info with fallback field mappings
- `try_alternative_mappings()`: Attempt alternative field name mappings

### 3. Rate Limiting Status Handler

**Purpose**: Fix async/await issues in rate limiting status retrieval

**Interface**:
```python
class RateLimitingStatusHandler:
    @staticmethod
    def get_status_safely(rate_limiter: EnhancedRateLimiter) -> Dict[str, Any]
    
    @staticmethod
    def format_status_display(status: Dict[str, Any]) -> str
```

**Key Methods**:
- `get_status_safely()`: Retrieve rate limiter status without async/await errors
- `format_status_display()`: Format status information for display

## Data Models

### ResponseStructureInfo

```python
@dataclass
class ResponseStructureInfo:
    format_type: ResponseFormatType
    has_attributes: bool
    available_fields: List[str]
    nested_structure: Dict[str, Any]
    sample_record: Optional[Dict[str, Any]]
```

### ResponseFormatType

```python
class ResponseFormatType(Enum):
    STANDARD = "standard"  # Expected format with 'attributes'
    FLAT = "flat"          # Flattened structure without 'attributes'
    NESTED = "nested"      # Deeply nested structure
    ALTERNATIVE = "alternative"  # Different field names
```

### ValidationResult Enhancement

```python
@dataclass
class EnhancedValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    processed_count: int
    failed_count: int
    structure_info: Optional[ResponseStructureInfo]
    sample_failures: List[Dict[str, Any]]
```

## Error Handling

### Validation Error Strategy

1. **Continue Processing**: Don't fail entire collection for individual record issues
2. **Detailed Logging**: Log specific field-level errors with sample data
3. **Fallback Extraction**: Attempt alternative field mappings
4. **Structure Analysis**: Analyze and log actual response structure

### Rate Limiting Error Prevention

1. **Sync Method Detection**: Identify synchronous methods and avoid `await`
2. **Error Wrapping**: Wrap status retrieval in try-catch blocks
3. **Graceful Degradation**: Continue operation even if status retrieval fails

## Testing Strategy

### Unit Tests

1. **Response Analysis Tests**:
   - Test structure detection with various response formats
   - Verify field mapping detection
   - Test logging output for debugging

2. **Enhanced Validation Tests**:
   - Test validation with missing 'attributes' fields
   - Test fallback extraction strategies
   - Test error reporting and continuation

3. **Rate Limiting Fix Tests**:
   - Test status retrieval without async/await errors
   - Test error handling for status failures
   - Test display formatting

### Integration Tests

1. **End-to-End Collection Tests**:
   - Test collection with various API response formats
   - Test error recovery and continuation
   - Test rate limiting status display

2. **Error Scenario Tests**:
   - Test handling of completely malformed responses
   - Test partial validation failures
   - Test rate limiter unavailability

## Implementation Approach

### Phase 1: Response Analysis Enhancement

1. Create `ResponseAnalyzer` class with structure detection
2. Enhance logging in `NewPoolsCollector` to use analyzer
3. Add detailed error reporting for validation failures

### Phase 2: Validation Resilience

1. Create `EnhancedNewPoolsValidator` with fallback strategies
2. Implement alternative field mapping attempts
3. Update `_extract_pool_info()` to use resilient extraction

### Phase 3: Rate Limiting Fix

1. Remove `await` from `get_status()` calls in CLI code
2. Add error handling for status retrieval failures
3. Test rate limiting status display functionality

### Phase 4: Integration and Testing

1. Update integration tests to cover new scenarios
2. Add comprehensive error scenario testing
3. Validate improved error reporting and resilience