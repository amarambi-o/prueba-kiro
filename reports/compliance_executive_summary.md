# Regulatory Compliance Assessment — Executive Summary
## payments-core | BankDemo | Bank Modernization Readiness Advisor

| | |
|---|---|
| System | payments-core |
| Database | BankDemo / SQL Server |
| Assessment Date | March 2026 |
| Classification | Confidential — Executive Use Only |
| Tool | Kiro + AWS MCP |

---

## Compliance Dashboard

| Dimension | Score | Status |
|---|---:|---|
| Regulatory Risk | 44 / 100 | 🟡 MEDIUM RISK |
| PCI-DSS Readiness | 56 / 100 | 🟡 PARTIAL |
| SOX Traceability | 89 / 100 | 🟢 ADEQUATE |
| PII Exposure Risk | 72 / 100 | 🔴 HIGH EXPOSURE |
| Encryption Coverage | 35 / 100 | 🔴 INSUFFICIENT |
| Auditability | 87 / 100 | 🟢 ADEQUATE |

---

## Risk Assessment

The payments-core system presents a **medium regulatory risk profile**
based on automated analysis of 700 payment records (108 records with critical data quality issues, 15.4% error rate).

The assessment identified **130 compliance findings** across 4 regulatory frameworks
(108 critical, 19 high severity), indicating that the system requires
structured remediation before it can be considered compliant with applicable banking regulations.

### Key Risk Drivers

| Finding | Severity | Framework | Impact |
|---|---|---|---|
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| MISSING_PAYMENT_ID | CRITICAL | SOX, PCI-DSS | payment_id is null — transaction cannot be individually audited... |
| INVALID_AMOUNT | CRITICAL | SOX, PCI-DSS | amount='-100.0' — financial integrity violation... |


---

## Compliance Gaps by Framework


### Basel III
- **NULL_TIMESTAMP** (MEDIUM): Field 'created_at' is null in 29 records — audit trail incomplete
- **NULL_TIMESTAMP** (MEDIUM): Field 'updated_at' is null in 26 records — audit trail incomplete
- **MISSING_SOURCE_SYSTEM** (MEDIUM): source_system is null in 109 records — data lineage cannot be established


### GDPR
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **PLAINTEXT_PII_FIELD** (HIGH): Field 'customer_name' contains 607 plaintext PII values — encryption at rest required
- **PLAINTEXT_PII_FIELD** (HIGH): Field 'customer_email' contains 642 plaintext PII values — encryption at rest required


### PCI-DSS
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **MISSING_CUSTOMER_IDENTITY** (HIGH): Both customer_name and customer_email are null — customer cannot be identified
- **PLAINTEXT_PII_FIELD** (HIGH): Field 'customer_name' contains 607 plaintext PII values — encryption at rest required
- **PLAINTEXT_PII_FIELD** (HIGH): Field 'customer_email' contains 642 plaintext PII values — encryption at rest required
- **INVALID_TRANSACTION_STATUS** (HIGH): 119 records have null or unrecognized status — transaction lifecycle integrity at risk


### SOX
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **MISSING_PAYMENT_ID** (CRITICAL): payment_id is null — transaction cannot be individually audited
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='nan' — financial integrity violation
- **INVALID_AMOUNT** (CRITICAL): amount='-100.0' — financial integrity violation
- **NULL_TIMESTAMP** (MEDIUM): Field 'created_at' is null in 29 records — audit trail incomplete
- **NULL_TIMESTAMP** (MEDIUM): Field 'updated_at' is null in 26 records — audit trail incomplete
- **MISSING_SOURCE_SYSTEM** (MEDIUM): source_system is null in 109 records — data lineage cannot be established
- **INVALID_TRANSACTION_STATUS** (HIGH): 119 records have null or unrecognized status — transaction lifecycle integrity at risk



---

## Migration Complexity Assessment

| Dimension | Current State | Target State | Complexity |
|---|---|---|---|
| Authentication | None | Amazon Cognito + IAM | High |
| Secrets Management | Hardcoded credentials | AWS Secrets Manager | Medium |
| Encryption at Rest | None (plaintext PII) | AWS KMS + RDS encryption | High |
| Audit Logging | None | AWS CloudTrail + CloudWatch | Medium |
| Data Lineage | Absent | AWS Glue + Lake Formation | High |
| PCI-DSS Controls | Insufficient | WAF + VPC + Security Groups | High |
| SOX Traceability | Partial | CloudTrail + Athena audit queries | Medium |

**Overall Migration Complexity: HIGH** — The system requires foundational security and compliance
controls to be implemented before or during cloud migration. A phased approach is strongly recommended.

---

## Recommended AWS Architecture

The following AWS services directly address the identified compliance gaps:

```
┌─────────────────────────────────────────────────────────┐
│  PERIMETER & ACCESS CONTROL                             │
│  AWS WAF → Application Load Balancer → Amazon Cognito   │
│  AWS IAM (least-privilege roles per service)            │
├─────────────────────────────────────────────────────────┤
│  COMPUTE                                                │
│  Amazon EKS (containerized payments-core microservices) │
├─────────────────────────────────────────────────────────┤
│  DATA LAYER                                             │
│  Amazon RDS for SQL Server (encrypted, Multi-AZ)        │
│  Amazon S3 (SSE-KMS encryption for all zones)           │
│  AWS KMS (key management for PII fields)                │
├─────────────────────────────────────────────────────────┤
│  SECRETS & CONFIGURATION                                │
│  AWS Secrets Manager (DB credentials, API keys)         │
│  AWS Systems Manager Parameter Store                    │
├─────────────────────────────────────────────────────────┤
│  AUDIT & COMPLIANCE                                     │
│  AWS CloudTrail (all API calls — SOX evidence)          │
│  Amazon CloudWatch (operational metrics + alerts)       │
│  Amazon Athena (audit queries over CloudTrail logs)     │
│  AWS Config (compliance rules — PCI-DSS, CIS)           │
├─────────────────────────────────────────────────────────┤
│  DATA GOVERNANCE                                        │
│  AWS Glue Data Catalog (data lineage)                   │
│  AWS Lake Formation (column-level access control)       │
│  Amazon Macie (PII detection and classification)        │
└─────────────────────────────────────────────────────────┘
```

### Priority Remediation Actions

| Priority | Action | AWS Service | Addresses |
|---|---|---|---|
| P1 — Immediate | Encrypt PII fields at rest | AWS KMS + RDS encryption | PCI-DSS, GDPR |
| P1 — Immediate | Implement audit logging | AWS CloudTrail | SOX, Basel III |
| P1 — Immediate | Remove hardcoded credentials | AWS Secrets Manager | PCI-DSS |
| P2 — Short term | Implement authentication layer | Amazon Cognito + IAM | PCI-DSS, SOX |
| P2 — Short term | Establish data lineage | AWS Glue + Lake Formation | SOX, Basel III |
| P3 — Medium term | PII classification and masking | Amazon Macie + KMS | GDPR, PCI-DSS |
| P3 — Medium term | Continuous compliance monitoring | AWS Config + Security Hub | All frameworks |

---

## Recommended Next Steps

1. **Engage executive sponsor** to approve compliance remediation program
2. **Prioritize P1 actions** — encryption and audit logging can be implemented within 30 days
3. **Initiate PCI-DSS gap assessment** with qualified security assessor (QSA)
4. **Design target AWS architecture** incorporating all controls listed above
5. **Establish data governance framework** before migrating to cloud

---

*Generated by Bank Modernization Readiness Advisor — Kiro + AWS MCP*
*Source evidence: clean/payments_clean.csv · errors/payments_errors.csv · output/data_quality_snapshot.json · output/readiness_score.json*
*Classification: Confidential — Executive Use Only | March 2026*
