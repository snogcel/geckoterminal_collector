
# Requirements Document

## Introduction
"The QLib integration layer currently has a critical issue with symbol generation and lookup that affects the reliability of data export and retrieval. Cryptocurrency addresses are case-sensitive, but the current implementation loses case information during symbol processing, breaking reverse lookups and data integrity. This feature addresses the case-sensitivity issue to ensure reliable symbol-to-pool mapping in the QLib integration."

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




##### END Requirements Document #

##### START v2 Document




### Requirement 1:

# Business Requirement:



The existing SDK already provides a method to maintain cryptographic address case-sensitivity requirements for QLib integration.

TODO:
- Identify what part of the process Kiro got stuck exporting data to QLib. **case_sensitivity_issue**

TODO
- Troubleshoot new bug that popped up in CLI command (dataframe to dict issue I believe) **test_coverage_issue**

Process:
- Fetch new pools using get_new_pools_by_network SDK call on a scheduled basis.
await client.get_new_pools_by_network("solana")

- Populate Pools table with this information to resolve Foreign Key constraint.
id: solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
address: jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
name: "TTT / SOL"
dex_id: "pumpswap"
base_token_id: solana_9oZzjkRV6bjKP5EHnnavgNkjj55LTn9gKNkeZiXepump
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 4943.8875
created_at: "2025-09-08T20:09:26Z"
last_updated: 

- Utilize new table "pool_data" to create historic records of get_new_pools_by_network
id: "solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU"
type: "pool"
name: "TTT / SOL"
base_token_price_usd: "0.00000624"
base_token_price_native_currency: "0.00000003"
quote_token_price_usd: "215.4862309"
quote_token_price_native_currency: "1"
address: "jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU"
reserve_in_usd: "4943.8875"
pool_created_at: "2025-09-09T21:27:52Z"
fdv_usd: "6235.663542"
market_cap_usd:
price_change_percentage_h1: "1.758"
price_change_percentage_h24: "1.758"
transactions_h1_buys: "5"
transactions_h1_sells: "4"
transactions_h24_buys: "5"
transactions_h24_sells: "4"
volume_usd_h24: "793.735054"
dex_id: "pump-fun"
base_token_id: "solana_9oZzjkRV6bjKP5EHnnavgNkjj55LTn9gKNkeZiXepump" # spent days looking for this one! lmao
quote_token_id: "solana_So11111111111111111111111111111111111111112"




# fetch new pools / tokens across solana network, not just a specific dex
await client.get_new_pools_by_network("solana")
# TODO -- map out new schema here


# Old Method: utilizes get_new_pools_by_network_dex (see below, schema for Pools table)

id: solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
address: jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
name: "TTT / SOL"
dex_id: "pumpswap"
base_token_id: solana_9oZzjkRV6bjKP5EHnnavgNkjj55LTn9gKNkeZiXepump
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 4943.8875
created_at: "2025-09-08T20:09:26Z"
last_updated: 

TODO: Should this replace the existing get_new_pools_by_network_dex method? Likely, will consult with Kiro.
TODO: QA - tie in findings from test coverage, fixed test relating to tests/test_dex_monitoring_collector.py
- Completed tests/test_dex_monitoring_collector.py

### END Requirement 1

















## Backburner

# Fetch Network Addresses:

await client.get_multiple_pools_by_network("solana", ["jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU", "D8ZkcRGLQwtsbJzy7qKKuVoV9sJfV3eMY5iuXYtcSiq7"])

pool_address: jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
network_address:

pool_address: D8ZkcRGLQwtsbJzy7qKKuVoV9sJfV3eMY5iuXYtcSiq7
network_address: 

id,type,name,base_token_price_usd,base_token_price_native_currency,quote_token_price_usd,quote_token_price_native_currency,address,reserve_in_usd,pool_created_at,fdv_usd,market_cap_usd,price_change_percentage_h1,price_change_percentage_h24,transactions_h1_buys,transactions_h1_sells,transactions_h24_buys,transactions_h24_sells,volume_usd_h24,dex_id,base_token_id,quote_token_id
solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU,pool,TTT / SOL,0.000006235663542054328541582313024017431448515970328535615467092592,0.0000000289376426375097,215.48623086427588499322276724390615758130980336,1.0,jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU,4943.8875,2025-09-09T21:27:52Z,6235.663542,,1.758,1.758,5,4,5,4,793.7350540025,pump-fun,solana_9oZzjkRV6bjKP5EHnnavgNkjj55LTn9gKNkeZiXepump,solana_So11111111111111111111111111111111111111112
solana_D8ZkcRGLQwtsbJzy7qKKuVoV9sJfV3eMY5iuXYtcSiq7,pool,imagine / SOL,0.00000604701644587822808222692070709006474350974666983040948740754509,0.0000000280330025034423,215.710623403101179568800295640674613781906581967,1.0,D8ZkcRGLQwtsbJzy7qKKuVoV9sJfV3eMY5iuXYtcSiq7,4792.9874,2025-09-09T21:27:50Z,6047.016446,,-4.698,-4.698,16,14,16,14,2982.9986931629,pump-fun,solana_AazcY9KDXD7ti6sfTGD6etrychuRupN4J36QnNapump,solana_So11111111111111111111111111111111111111112
