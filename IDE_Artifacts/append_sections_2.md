import os

DOCS_DIR = "/home/pi-net/Documents/agent_eng_labs/Agent-with-RAG/sample_docs"

# Additional sections for company_marketing_strategy.md
marketing_addon = """
---

## 11. Enterprise Channel Partner and Global System Integrator (GSI) Strategy

While direct sales and product-led adoption form the core of our acquisition engine, indirect channel partnerships represent the primary multiplier for scaling into the Global 2000. Large enterprise transformations are rarely conducted in isolation; multinational corporations routinely contract Global System Integrators (GSIs) such as Accenture, Deloitte, Capgemini, and Wipro to architect and deploy their modern AI infrastructure.

### 11.1 GSI Tiering and Partner Enablement Framework

Nexus classifies partners into three strategic tiers, each with tailored commercial terms, technical enablement resources, and co-marketing commitments:

```
+----------------------------------------------------------------------------------+
|                      GSI Partner Tiering & Certification Matrix                  |
+----------------------------------------------------------------------------------+
| Criteria / Benefit          Registered Partner   Gold Partner   Platinum Partner |
| -------------------------------------------------------------------------------- |
| Minimum Certified Architects 2 Architects        10 Architects  25+ Architects   |
| Annual Co-Sell Pipeline     $ 2.0M               $ 10.0M        $ 35.0M+         |
| Co-Op Marketing Budget Fund $ 15k                $ 75k          $ 250k           |
| Dedicated Partner Exec      Regional Pool        Dedicated Mgr  Global VP Lead   |
| Margin / Referral Rebate    12% Referral         18% Margin     25% Margin       |
| Joint Customer Case Studies Optional             1 Per Annum    3+ Per Annum     |
+----------------------------------------------------------------------------------+
```

1. **Nexus Certified Architect Academy:** A rigorous multi-week technical curriculum validating an engineer's mastery over distributed vector databases, FastMCP integration, and zero-trust container security. By certifying over 1,200 GSI consultants across North America and Europe, we create an army of external advocates who embed Nexus as the default architecture in enterprise client RFPs.
2. **Joint Solution Blueprints:** Co-authored architectural blueprints tailored to regulated industry verticals. For instance, the *Nexus-Deloitte Financial Services Reference Architecture* provides pre-packaged compliance frameworks for banking clients implementing automated loan underwriting and fraud detection agents.
3. **Co-Selling Alignment:** Partner account managers are paired directly with enterprise field sales representatives. Compensation plans are explicitly structured with neutral commissions, ensuring direct sales teams are incentivized to collaborate with GSIs rather than compete against them.

---

## 12. Customer Lifecycle Marketing, Expansion Playbooks, and Retention Engineering

Sustaining a Dollar-Based Net Retention Rate (NRR) of 132% requires a systematic, data-driven approach to customer success and lifecycle marketing. Customer churn and contraction are actively prevented through automated telemetry monitoring and proactive value delivery.

### 12.1 The Customer Success Telemetry Health Score

Nexus engineering streams real-time operational telemetry into our customer data platform, calculating a dynamic Customer Health Score (0–100) updated daily:

- **Deployment Health (30% Weight):** Evaluates system uptime, query error rates, and API latency percentiles (p95, p99). Any sustained degradation triggers an immediate PagerDuty alert to the assigned Technical Account Manager (TAM).
- **Consumption Velocity (40% Weight):** Tracks weekly active queries, indexed vector volume, and token expenditures relative to contractual thresholds. An unexpected 20% drop in weekly consumption flags an account for immediate intervention.
- **Organizational Breadth (30% Weight):** Measures the number of active developer seats, internal departments, and unique applications interacting with the Nexus platform. Broad multi-departmental adoption correlates with an annual churn rate under 1.8%.

```
+----------------------------------------------------------------------------------+
|                    Customer Expansion & EBR Operating Rhythm                     |
+----------------------------------------------------------------------------------+
| Timeline   Milestone                 Key Marketing / Success Deliverable         |
| ---------- ------------------------- ------------------------------------------- |
| Day 1–30   Onboarding & Baseline     Kickoff workshop, architecture review, SLA  |
| Day 60     First Value Milestone     Initial agent workflow live in production   |
| Day 90     Executive Business Review Value verification against original ROI model|
| Day 180    Mid-Year Horizon Audit    Departmental expansion discovery & roadmap  |
| Day 270    Pre-Renewal Scoping       Multi-year contract proposal & tier upgrade |
| Day 360    Seamless Renewal          Expansion agreement executed; case study PR |
+----------------------------------------------------------------------------------+
```

---

## 13. Public Relations, Crisis Communications, and Brand Safety

In an era of intense public scrutiny regarding artificial intelligence ethics, model bias, and corporate data privacy, maintaining an impeccable brand reputation is an essential commercial safeguard. Nexus enforces strict governance protocols across all public communications and technical disclosures.

### 13.1 Ethical AI and Transparency Charter

Nexus pledges unambiguous adherence to our published Ethical AI Principles:
- **Zero Proprietary Data Harvesting:** Customer data, vector embeddings, and inference payloads are never utilized to train global foundation models. All tenant spaces remain cryptographically sealed.
- **Verifiable Grounding & Citation:** The platform strictly enforces citation tracing, ensuring that autonomous agent answers are grounded in explicit source documentation.
- **Environmental Carbon Offsetting:** We calculate the aggregate megawatt-hours consumed across our cloud infrastructure and invest in verified renewable energy credits to achieve net-zero operational carbon emissions.

### 13.2 Rapid-Response Incident Management Protocol

In the event of an infrastructure disruption, security vulnerability disclosure, or unexpected platform anomaly, the Marketing Communications team executes a structured incident management protocol:
1. **Initial Disclosure Within 15 Minutes:** Publishing a transparent acknowledgment on the public Nexus Status Page (`status.nexus-tech.internal`) detailing affected regions, error signatures, and active triage steps.
2. **Direct Enterprise Notification:** Automated email alerts and Slack webhook broadcasts dispatched to designated customer security and infrastructure contacts.
3. **Comprehensive Post-Mortem Publication:** Publishing an exhaustive root-cause analysis (RCA) within 72 hours, authored by senior systems engineering and approved by the Chief Information Security Officer, detailing the exact timeline, root failure mechanics, and long-term architectural remediations implemented to prevent recurrence.
"""

# Additional sections for financial_report.md
financial_addon = """
---

## 11. Notes to Consolidated Financial Statements and Accounting Disclosures

### Note 1: Organization and Significant Accounting Policies

Nexus Technologies Corporation (the "Company") was incorporated in the State of Delaware in October 2021. The Company provides an enterprise-grade cloud software platform and autonomous agent orchestration architecture enabling organizations to synthesize, retrieve, and operationalize enterprise knowledge bases with deterministic accuracy and security.

**Basis of Presentation:** The accompanying consolidated financial statements have been prepared in accordance with accounting principles generally accepted in the United States of America ("U.S. GAAP") and pursuant to the rules and regulations of the Securities and Exchange Commission ("SEC"). The consolidated financial statements include the accounts of the Company and its wholly-owned subsidiaries. All intercompany accounts and transactions have been eliminated in consolidation.

**Use of Estimates:** The preparation of consolidated financial statements requires management to make estimates and assumptions that affect the reported amounts of assets and liabilities and disclosure of contingent assets and liabilities at the date of the financial statements and the reported amounts of revenues and expenses during the reporting period. Significant estimates include standalone selling prices for multi-element revenue arrangements, valuation allowance for deferred tax assets, useful lives of property and intangible assets, and the fair value of stock-based awards. Actual results could differ from those estimates.

### Note 2: Revenue Recognition and Contract Balances (ASC 606)

The Company recognizes revenue in accordance with ASC Topic 606, *Revenue from Contracts with Customers*. Revenue is recognized when control of promised software subscriptions, cloud services, or professional advisory services is transferred to customers in an amount that reflects the consideration the Company expects to be entitled to receive in exchange for those services.

```
Contract Balances Summary:
(In thousands of USD)
As of December 31,
                                                      2025            2024
Accounts receivable, gross                        $  25,400       $  17,350
Less: Allowance for credit losses                      (550)           (430)
Accounts receivable, net                          $  24,850       $  16,920

Deferred revenue, current                         $  48,600       $  34,200
Deferred revenue, non-current                         3,400           2,800
Total Deferred Revenue                            $  52,000       $  37,000
```

Deferred revenue consists of customer billings received in advance of service performance under subscription agreements. The increase in deferred revenue of $15.0 million during fiscal year 2025 reflected expanded customer additions and annual multi-year contract renewals. During fiscal year 2025, the Company recognized $33.8 million of revenue that was included in the deferred revenue balance as of December 31, 2024.

---

## 12. Stock-Based Compensation and Equity Incentive Programs

The Company maintains the 2021 Equity Incentive Plan (the "2021 Plan"), providing for the grant of incentive stock options, non-statutory stock options, restricted stock units (RSUs), and performance-based awards to employees, officers, and directors.

### 12.1 Valuation Assumptions and Option Activity

The fair value of employee stock option grants is estimated on the date of grant using the Black-Scholes-Merton option-pricing model based on the following weighted-average assumptions:

```
+-----------------------------------------------------------------------------------+
|               Black-Scholes-Merton Valuation Model Assumptions                    |
+-----------------------------------------------------------------------------------+
| Assumption                      Year Ended Dec 31, 2025   Year Ended Dec 31, 2024 |
| --------------------------------------------------------------------------------- |
| Expected volatility             48.5%                     52.0%                   |
| Expected term (in years)        5.6 years                 5.8 years               |
| Risk-free interest rate         3.85%                     4.10%                   |
| Expected dividend yield         0.0%                      0.0%                    |
| Weighted-average grant date FV  $ 12.45                   $ 8.90                  |
+-----------------------------------------------------------------------------------+
```

Total stock-based compensation expense recognized across the Consolidated Statements of Operations was categorized as follows:
- Cost of revenue: $ 1,420,000 (FY2024: $ 980,000)
- Research & development: $ 7,650,000 (FY2024: $ 6,100,000)
- Sales & marketing: $ 3,130,000 (FY2024: $ 2,620,000)
- General & administrative: $ 2,000,000 (FY2024: $ 1,700,000)
Total stock-based compensation expense: $ 14,200,000 (FY2024: $ 11,400,000)

As of December 31, 2025, there was approximately $28.4 million of total unrecognized stock-based compensation expense related to unvested awards, which is expected to be recognized over a weighted-average period of 2.7 years.

---

## 13. Income Taxes and Deferred Tax Asset Valuation

The provision for (benefit from) income taxes consisted of the following:

```
(In thousands of USD)
Years Ended December 31,
                                                      2025            2024
Current:
  Federal                                         $   1,850       $     120
  State and local                                       420              80
  Foreign jurisdictions                                 180             150
Total Current Tax Expense                             2,450             350

Deferred:
  Federal                                                --            (800)
  State and local                                        --            (200)
Total Deferred Tax Benefit                               --          (1,000)
Total Provision for (Benefit from) Income Taxes   $   2,450       $    (650)
```

The Company's effective tax rate for fiscal 2025 was 13.0%, compared to 12.3% in fiscal 2024. The difference between the statutory federal income tax rate of 21.0% and the effective tax rate reflects research and development tax credits, foreign rate differentials, and changes in the valuation allowance against deferred tax assets.

As of December 31, 2025, the Company had federal net operating loss (NOL) carryforwards of approximately $38.2 million, which have an indefinite carryforward period, and state NOL carryforwards of $26.4 million, which begin to expire in 2038. Management assesses the realizability of deferred tax assets on a regular basis and maintains a partial valuation allowance where realization is not deemed more likely than not.

---

## 14. Legal Proceedings and Contingent Liabilities

From time to time, the Company may be involved in legal proceedings, claims, and regulatory inquiries arising in the ordinary course of business, including matters related to employment practices, commercial contracts, and intellectual property. 

As of December 31, 2025, the Company was not party to any material pending litigation or legal proceedings that, in the opinion of management and outside legal counsel, would have a material adverse effect on our business, financial position, results of operations, or cash flows. The Company records a liability when an adverse outcome is probable and the amount of loss can be reasonably estimated. No accruals for contingent legal liabilities were required at year-end.
"""

def append_to_file(filename, addon):
    filepath = os.path.join(DOCS_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        existing = f.read()
    new_content = existing.strip() + "\n" + addon.strip() + "\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    words = len(new_content.split())
    print(f"Updated {filename}: {words} words")

append_to_file("company_marketing_strategy.md", marketing_addon)
append_to_file("financial_report.md", financial_addon)
