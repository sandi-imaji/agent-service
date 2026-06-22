## Diagnostic Summary
- **Timestamp**: 2026-06-17 14:25:38 (elapsed: 19.14s)
- **Overall Status**: OK
- **Detail**: Failover successful - PRIMARY had mismatch (Mismatch: Expected SL [20.7] but got ModScan [21.400000000000002]), SECONDARY value matches SL
- **Active Connection**: SECONDARY
- **Tagname**: CRAH-2DH2.1-RETURN_AIR_TEMP

## Network Status
| Layer | Status | Detail | Time |
|-------|--------|--------|------|
| PING | OK | Success - 10.25.17.44 | 14:25:38 |
| TELNET | OK | Success - 10.25.17.44:502 | 14:25:38 |

## Value Comparison Trail
| Connection | ModScan Value | SL Value | Difference | Status |
|------------|---------------|----------|------------|--------|
| PRIMARY | N/A | N/A | N/A | MISMATCH |
| SECONDARY | 20.700000000000003 | N/A | N/A | OK |

**Smartlink Detail**: Match SL and ModScan Values are both 20.7

## Failover Tracking
- **Triggered**: Yes
- **Primary Mismatch Detail**: Mismatch: Expected SL [20.7] but got ModScan [21.400000000000002]
- **Final Connection Used**: SECONDARY

## Register Data
- **Current Value**: 20.700000000000003
- **Data Type**: int16
- **Hex Representation**: cf00
- **Binary**: 0000000011001111

## Configuration
- **Primary**: 10.25.17.44:502
- **Secondary**: 10.25.17.64:502
- **Device ID**: 1
- **Register Address**: 40977
- **Point Type**: PointType.HOLDING_REGISTER
- **Byte Order**: Little Endian
- **Swapped**: No
- **Timeout**: 5.0s
- **Retries**: 2
- **Bit Position**: 0
- **Precision**: 0
- **Factor**: 0.1
- **Offset**: 0

## Analysis & Recommendations
1. Status: OK
2. Issue: None
3. Action: No action required. The system is operating normally on the secondary connection with a slight misalignment in the measured values, but the values still match the expected range.