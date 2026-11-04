"""Generate fictional supplier RFP responses (all names and data are invented).

Run:  python scripts/generate_sample_rfps.py
Creates sample_rfps/*.pdf (10+ pages each) plus an intentionally blank PDF for the validation demo.
"""
from __future__ import annotations

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample_rfps")
RFP_REF = "RFP MRWB-2026-014: Customer Service and Billing Platform Modernisation"
BUYER = "Meridian Regional Water Board (fictional)"
W = 174 * mm  # usable width

styles = getSampleStyleSheet()
BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9.8, leading=13.5, spaceAfter=5)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=12, bulletIndent=2)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=10, textColor=colors.grey, spaceAfter=10)
H3 = ParagraphStyle("H3", parent=BODY, fontName="Helvetica-Bold", fontSize=10.5, spaceBefore=6, spaceAfter=3)


def table(rows, widths, accent):
    t = Table(rows, colWidths=[w * W for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C2CC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F8")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def wrap_rows(rows):
    cell = ParagraphStyle("cell", parent=BODY, fontSize=8.6, leading=11, spaceAfter=0)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    return [[Paragraph(str(c), head if i == 0 else cell) for c in r] for i, r in enumerate(rows)]


def make_canvas(supplier_name, accent):
    """Canvas that draws a header and a 'Page X of Y' footer (needs the total, so pages are buffered)."""
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for state in self._saved:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total):
            self.saveState()
            if self._pageNumber > 1:
                self.setFillColor(accent)
                self.setFont("Helvetica-Bold", 8.5)
                self.drawString(18 * mm, A4[1] - 11 * mm, supplier_name)
                self.setFillColor(colors.grey)
                self.setFont("Helvetica", 8)
                self.drawRightString(A4[0] - 18 * mm, A4[1] - 11 * mm, "Response to RFP MRWB-2026-014")
                self.setStrokeColor(accent)
                self.line(18 * mm, A4[1] - 13 * mm, A4[0] - 18 * mm, A4[1] - 13 * mm)
            self.setFillColor(colors.grey)
            self.setFont("Helvetica", 8)
            self.drawString(18 * mm, 9 * mm, f"{supplier_name} | Confidential | Fictional exercise document")
            self.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {self._pageNumber} of {total}")
            self.restoreState()
    return NumberedCanvas


def build(supplier: dict) -> str:
    path = os.path.join(OUT_DIR, supplier["file"])
    accent = colors.HexColor(supplier["accent"])
    H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=26, leading=30, textColor=accent, alignment=0)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13.5, spaceBefore=12, spaceAfter=5, textColor=accent)
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=20 * mm, bottomMargin=17 * mm,
                            title=f"{supplier['name']} - Proposal", author=supplier["name"])
    name = supplier["name"]
    story = [Spacer(1, 45 * mm), Paragraph(name, H1),
             Paragraph("Technical and Commercial Proposal", ParagraphStyle("c2", parent=H1, fontSize=17, leading=21)),
             Spacer(1, 8 * mm),
             Paragraph(f"Response to {RFP_REF}", ParagraphStyle("c3", parent=BODY, fontSize=12, leading=16)),
             Paragraph(f"Issued by: {BUYER}", BODY),
             Paragraph(f"Submitted: {supplier['date']}", BODY),
             Spacer(1, 12 * mm)]
    story += [table(wrap_rows(supplier["cover"]), [0.32, 0.68], accent), Spacer(1, 40 * mm),
              Paragraph("<i>This is a fictional proposal created for a classroom exercise. All organisations, people "
                        "and figures are invented.</i>", SUB), PageBreak()]
    # table of contents (section titles; pagination left to the reader)
    story.append(Paragraph("Table of Contents", H2))
    for sec in supplier["sections"]:
        if sec != "PAGEBREAK":
            story.append(Paragraph(sec[0], ParagraphStyle("toc", parent=BODY, fontSize=10.5, leading=17)))
    story.append(Spacer(1, 6))
    for section in merged_sections(supplier):
        if section == "PAGEBREAK":
            story.append(PageBreak())
            continue
        title, content = section
        if title.split(".")[0] in supplier.get("break_before", ()):
            story.append(PageBreak())
        story.append(Paragraph(title, H2))
        for block in content:
            if isinstance(block, str):
                story.append(Paragraph(block, H3 if block.startswith("##") is False and False else BODY))
            elif block[0] == "h":
                story.append(Paragraph(block[1], H3))
            elif block[0] == "bullets":
                story += [Paragraph(b, BULLET, bulletText="-") for b in block[1]]
            elif block[0] == "table":
                story += [table(wrap_rows(block[1]), block[2], accent), Spacer(1, 6)]
    story += [Spacer(1, 10), Paragraph("<i>End of proposal. This is a fictional proposal created for a classroom "
                                       "exercise; all organisations, people and figures are invented.</i>", SUB)]
    doc.build(story, canvasmaker=make_canvas(name, accent))
    return path


def H(t):
    return ("h", t)


def B(*items):
    return ("bullets", list(items))


def T(rows, widths):
    return ("table", rows, widths)


SUPPLIERS = [
    # ------------------------------------------------------------ APEX: strong tech + security, high price
    {
        "name": "Apex Systems", "file": "Apex_Systems_Proposal.pdf", "date": "2026-10-20", "accent": "#0B3D91",
        "cover": [["Item", "Detail"],
                  ["Bidder", "Apex Systems Pvt. Ltd., Pune, India"],
                  ["Proposed solution", "Apex UtilityCloud: cloud-native billing and customer service platform"],
                  ["Contract duration", "40 weeks implementation plus 3-year subscription"],
                  ["Total 3-year cost", "INR 14.21 Cr (fixed price implementation), excludes GST"],
                  ["Certifications", "ISO 27001:2022, SOC 2 Type II"],
                  ["Bid validity", "150 days from submission"]],
        "sections": [
            ("1. Executive Summary and Understanding of the Requirement", [
                "Apex Systems proposes a cloud-native Customer Service and Billing Platform for the Meridian Regional "
                "Water Board that replaces the 14-year-old legacy billing system and three disconnected customer "
                "service tools. Our solution is designed for 1.2 million service connections today and scales to "
                "3 million without re-architecture.",
                "Apex has deep engineering capability and a mature security programme. We hold ISO 27001:2022 and "
                "SOC 2 Type II attestations, and our platform has been independently penetration tested every six months "
                "since 2021. We believe security and resilience are non-negotiable for critical utility infrastructure.",
                H("What we understood from the RFP"),
                "The Board needs to consolidate billing, metering data, customer self-service and field-service "
                "workflows; integrate with SAP S/4HANA finance and the existing AMI meter data management system (MDM); "
                "comply with data protection obligations under the Digital Personal Data Protection (DPDP) Act; and reduce "
                "billing exceptions, currently around 4.5 percent of monthly bills.",
                "From the clarification session and the data room we also noted four constraints that shaped our design: "
                "(a) 14 years of customer history, roughly 38 million billing records, must be retained and searchable; "
                "(b) the Board operates 11 zone offices with uneven connectivity, so the agent desktop must degrade "
                "gracefully; (c) tariff policy changes twice a year and must be configurable by Board staff without "
                "vendor involvement; and (d) the billing run window is 8 hours overnight and must not extend.",
                H("Why Apex"),
                B("Security first: ISO 27001:2022 and SOC 2 Type II, with VAPT every six months and a 1-hour breach notification commitment.",
                  "Engineering depth: 62 platform engineers, a dedicated utilities product team and a 99.95 percent measured availability over the last 24 months.",
                  "Clear commercials: fixed-price implementation, published rate card, no open-ended time-and-materials exposure for the Board.",
                  "Proven utility delivery: 6 utility billing implementations in 8 years, including two water utilities."),
                H("Value proposition summary"),
                T([["Board objective", "How Apex addresses it", "Measure"],
                   ["Reduce billing exceptions", "Pre-bill validation engine with 140 configurable rules and exception work queues",
                    "Exceptions from 4.5 percent to below 1.5 percent within 6 months of go-live"],
                   ["Faster bill cycle", "Parallelised billing engine, 12 worker pods per zone group", "1.2 million accounts billed in under 3 hours"],
                   ["Digital self-service", "Portal and mobile app in 4 languages with UPI payments", "Target 55 percent digital payment share by month 12"],
                   ["Regulatory compliance", "Consent management, India data residency, 7-year audit logs", "Zero audit findings at first annual review (target)"]],
                  [0.24, 0.46, 0.30]),
            ]),
            ("2. Proposed Solution and Architecture", [
                "The platform uses a microservices architecture deployed on Kubernetes across two cloud availability "
                "zones in an Indian region, with active-active failover and a recovery point objective (RPO) of 5 minutes "
                "and recovery time objective (RTO) of 30 minutes. Each domain service owns its data store; services "
                "communicate through Apache Kafka events and a REST API gateway.",
                B("Billing engine: rule-based tariff configuration supporting slab, seasonal and subsidy tariffs without code changes.",
                  "Integration layer: event streaming with Apache Kafka plus a REST API gateway; 42 pre-built connectors including SAP S/4HANA (IDoc and OData) and MDM via MultiSpeak.",
                  "Customer portal and mobile app: bill view, UPI payment, complaint tracking, outage notifications in English, Hindi and two regional languages.",
                  "Performance: load tested to 2,500 concurrent portal users and a full billing cycle of 1.2 million accounts in under 3 hours.",
                  "Data migration: automated reconciliation with 100 percent record-count and 99.98 percent value matching targets before cutover."),
                H("Logical architecture layers"),
                T([["Layer", "Components", "Technology and design notes"],
                   ["Channels", "Customer web portal, mobile app (Android and iOS), agent desktop, IVR gateway, WhatsApp notifications",
                    "React front end, server-side rendering for portal pages, offline-tolerant agent desktop with local queueing for 11 zone offices"],
                   ["API and integration", "API gateway, event bus, 42 connectors, orchestration service",
                    "Kong-class gateway with OAuth 2.0 and mTLS; Kafka with 3x replication, 30-day topic retention"],
                   ["Core services", "Billing, rating, payments, CRM and case management, field-service dispatch, notifications",
                    "Java 21 and Kotlin services on Kubernetes; stateless pods, horizontal autoscaling on queue depth"],
                   ["Data", "Operational store, analytics store, document store, search index",
                    "PostgreSQL clusters with synchronous replication inside a zone, asynchronous across zones; object storage for bill PDFs"],
                   ["Platform and security", "Identity, secrets, key management, observability, CI/CD",
                    "Customer-managed keys in HSM-backed KMS, OpenTelemetry tracing, GitOps deployment with signed images"]],
                  [0.17, 0.38, 0.45]),
                H("Resilience and scalability"),
                "Every stateful tier is replicated across two availability zones. Quarterly game-day exercises simulate "
                "zone loss, database failover and message-bus degradation. The billing engine scales from 12 to 48 worker "
                "pods during the monthly run and releases capacity afterwards. Capacity headroom is set at 2.5x the "
                "current peak, and the architecture was validated at 3 million connections in a synthetic test in "
                "August 2026 (billing cycle of 3 million accounts in 6 hours 40 minutes).",
                H("Configurability for Board staff"),
                "Tariff tables, rebate rules, late-fee policies and bill templates are maintained in an administration "
                "console with maker-checker approval and effective-dated versions. Board staff can simulate a tariff change "
                "against a sample of 50,000 historical accounts before publishing, and every change is written to the "
                "immutable audit log. Typical tariff revisions are completed in 2 working days without vendor involvement.",
            ]),
            ("3. Integration Approach", [
                "Integration is the highest technical risk in this programme, so we designed it early and in detail. "
                "The following integration specification reflects the interface documents shared in the RFP data room.",
                T([["Interface", "Direction", "Pattern and protocol", "Volume and timing"],
                   ["SAP S/4HANA finance (GL, AR)", "Outbound and inbound", "IDoc over RFC for postings; OData for balance enquiry; nightly reconciliation file as fallback",
                    "About 1.2 million posting lines per cycle; near-real-time for payments"],
                   ["AMI meter data management (MDM)", "Inbound", "MultiSpeak 5 web services for reads; Kafka ingestion for interval data; validation, estimation and editing rules",
                    "Up to 1.4 million reads per day; 15-minute interval data for 90,000 commercial meters"],
                   ["UPI and payment gateways", "Bidirectional", "REST and webhooks with idempotency keys; signed callbacks",
                    "Peak 120 transactions per second"],
                   ["SMS, email and WhatsApp gateways", "Outbound", "REST with delivery receipts; templated multilingual messages",
                    "Up to 2.4 million messages per cycle"],
                   ["Legacy billing (migration only)", "Inbound", "Read-only extract through staged flat files and database link; checksum-controlled",
                    "38 million historical billing records, three mock migrations"]],
                  [0.22, 0.14, 0.38, 0.26]),
                H("Integration governance"),
                "Each interface has a named owner on both sides, a signed interface control document by week 8, a "
                "contract-test suite that runs on every build, and a certification gate in week 26. A virtualised SAP and "
                "MDM simulator allows development to proceed before the Board's test environments are ready, which "
                "protects the schedule if environment delivery slips by up to three weeks.",
                H("Error handling"),
                "All integrations use at-least-once delivery with idempotent consumers, dead-letter queues and an "
                "operations console where support staff can inspect and replay failed messages. Alerts fire when any "
                "interface backlog exceeds 15 minutes.",
            ]),
            ("4. Implementation Approach", [
                "Delivery follows a phased hybrid approach: design waterfall for regulated billing rules, then agile "
                "two-week sprints for portal and integrations. Each phase ends with a documented exit review attended "
                "by the Board's PMO.",
                T([["Phase", "Key activities", "Exit criteria"],
                   ["1. Discovery and design", "Process workshops in all 11 zones, tariff catalogue, interface control documents, data profiling of legacy records",
                    "Signed solution design, tariff catalogue and migration strategy"],
                   ["2. Build and integration", "13 sprints; core billing, portal, mobile, SAP and MDM integrations; security hardening",
                    "SAP and MDM integrations certified; 92 percent of user stories accepted"],
                   ["3. Data migration", "Three mock migrations with automated reconciliation; cleansing of duplicate and orphan accounts",
                    "Mock 3 reconciles at 99.98 percent value match"],
                   ["4. Testing", "System integration test, UAT in 3 zones, performance test at 2,500 users, VAPT, disaster recovery test",
                    "UAT sign-off, no open Severity 1 or 2 defects, VAPT findings closed"],
                   ["5. Go-live and hypercare", "Zone-wise cutover over three weekends, 4 weeks hypercare with on-site support",
                    "Stable billing cycle, handover to run support"]],
                  [0.2, 0.52, 0.28]),
                H("Change management and training"),
                "A change network of 22 Board champions (two per zone office plus HQ) is trained in weeks 20-26. "
                "Training covers 30 train-the-trainer sessions, role-based e-learning modules and a sandbox environment. "
                "Super-users receive 5 days of training; agents receive 2 days. Training completion of 95 percent is "
                "an exit criterion for UAT.",
                H("Quality assurance"),
                "A test pyramid is enforced in the pipeline: at least 80 percent unit test coverage on billing "
                "services, 1,400 automated regression scenarios and a nightly performance smoke test. Defect "
                "severity definitions follow the SLA in Section 8.",
            ]),
            ("5. Timeline, Team Structure and Milestones", [
                "Total duration is 40 weeks. The plan below shows phase windows and the payment-linked milestones.",
                T([["Phase", "Weeks", "Key milestone"],
                   ["Discovery and design", "1-8", "Approved solution design and tariff catalogue"],
                   ["Build and integration", "9-26", "SAP and MDM integrations certified"],
                   ["Data migration rehearsals", "20-32", "Three mock migrations passed"],
                   ["UAT and performance testing", "27-36", "UAT sign-off"],
                   ["Go-live and hypercare", "37-40", "Go-live plus 4 weeks hypercare"]],
                  [0.32, 0.14, 0.54]),
                H("Team structure"),
                "Team: 1 delivery director, 1 project manager, 2 solution architects, 8 engineers, 2 QA leads and "
                "1 security architect (14 FTE at peak, 11 FTE average). A risk register is reviewed weekly with the "
                "Board's PMO and a steering committee meets monthly.",
                T([["Role", "FTE", "Responsibility", "Location"],
                   ["Delivery director", "0.3", "Executive sponsor, escalation, steering committee", "Pune"],
                   ["Project manager", "1.0", "Plan, risks, dependencies, reporting", "On site, Meridian HQ"],
                   ["Solution architects", "2.0", "Overall design, integration design, non-functional requirements", "1 on site, 1 Pune"],
                   ["Senior engineers", "8.0", "Billing, portal, integration, data migration", "Pune with rotating on-site presence"],
                   ["QA leads", "2.0", "Test strategy, automation, performance testing", "Pune"],
                   ["Security architect", "1.0", "Threat modelling, VAPT coordination, compliance evidence", "Pune"]],
                  [0.24, 0.08, 0.50, 0.18]),
                H("Governance"),
                "Weekly progress review with the Board's PMO, fortnightly sprint demonstrations, monthly steering "
                "committee, and a formal change control board. Status reports include earned-value indicators, defect "
                "trends and a RAG-rated risk list.",
                H("Top delivery risks"),
                T([["Risk", "Likelihood", "Mitigation"],
                   ["SAP or MDM test environments late", "Medium", "Virtualised simulators; environment booking in week 1; 3-week schedule buffer"],
                   ["Poor quality of legacy data", "High", "Profiling in weeks 3-6; two cleansing cycles; reconciliation gates"],
                   ["Tariff rules not frozen on time", "Medium", "Tariff freeze at design sign-off; change control after week 8"]],
                  [0.34, 0.14, 0.52]),
            ]),
            ("6. Commercial Proposal and Price Table", [
                T([["Item", "Price (INR)", "Notes"],
                   ["Implementation services (fixed price)", "6,80,00,000", "Milestone-based payments"],
                   ["Platform subscription, Year 1", "2,60,00,000", "Up to 1.5 million connections"],
                   ["Platform subscription, Year 2", "2,60,00,000", "Price held flat"],
                   ["Platform subscription, Year 3", "2,73,00,000", "5 percent uplift"],
                   ["Data migration and training", "48,00,000", "Includes 30 train-the-trainer sessions"],
                   ["Total 3-year cost", "14,21,00,000", "Excludes GST"]],
                  [0.40, 0.20, 0.40]),
                "Assumptions: the Board provides SAP integration test environments by week 9; tariff rules are frozen "
                "at design sign-off; change requests are charged at INR 18,500 per person-day. Payment terms are "
                "20 percent on design sign-off, 30 percent on UAT, 40 percent on go-live and 10 percent after hypercare.",
                H("Payment schedule for implementation services"),
                T([["Milestone", "Percent", "Amount (INR)"],
                   ["Design sign-off (week 8)", "20", "1,36,00,000"],
                   ["UAT sign-off (week 36)", "30", "2,04,00,000"],
                   ["Go-live (week 37)", "40", "2,72,00,000"],
                   ["After hypercare (week 40)", "10", "68,00,000"]],
                  [0.5, 0.2, 0.3]),
                H("Pricing basis and rate card"),
                "Our price is a fixed price for the scope described in this document. Subscription fees cover hosting "
                "in two availability zones, 24x7 support, platform upgrades and security monitoring. Fees for "
                "connections above 1.5 million are INR 14 per connection per month. Year-3 subscription includes a "
                "5 percent uplift; no other escalation applies in the 3-year term.",
                T([["Role (for change requests)", "Rate per person-day (INR)"],
                   ["Solution architect", "24,000"],
                   ["Senior engineer", "18,500"],
                   ["QA engineer", "14,000"],
                   ["Blended rate for change requests", "18,500"]],
                  [0.6, 0.4]),
                "We acknowledge that this is the highest-priced proposal in the market range we expect. The premium "
                "reflects dual-zone active-active hosting, 24x7 SIEM monitoring, six-monthly independent penetration "
                "testing and a larger delivery team (14 FTE at peak). We are open to discussing scope-based options, "
                "for example single-zone hosting for non-production environments, to reduce cost.",
            ]),
            ("7. Security, Compliance and Risk Controls", [
                B("Certifications: ISO 27001:2022 (certificate valid to 2028) and SOC 2 Type II report available under NDA.",
                  "Encryption: AES-256 at rest with customer-managed keys; TLS 1.3 in transit.",
                  "Access: MFA for all users, role-based access control and privileged access management with session recording.",
                  "Monitoring: 24x7 SIEM, immutable audit logs retained for 7 years, quarterly access reviews.",
                  "Privacy: DPDP Act consent management, data residency in India, data protection impact assessment in design phase.",
                  "Testing: independent VAPT before go-live and every six months; incident response plan with 1-hour notification."),
                H("Security governance"),
                "Security is led by a named security architect on the project and by Apex's Chief Information Security "
                "Officer at corporate level. Threat modelling (STRIDE) is performed for every major service during "
                "design, and secure coding standards aligned to OWASP ASVS Level 2 are enforced through static analysis, "
                "dependency scanning and signed container images. Production access is just-in-time, approved and recorded.",
                H("Risk register (security and operational)"),
                T([["Risk", "Impact", "Control", "Residual"],
                   ["Unauthorised access to customer data", "High", "MFA, RBAC, PAM with session recording, quarterly access review", "Low"],
                   ["Ransomware or destructive attack", "High", "Immutable backups every 15 minutes, offline copy daily, restore test each quarter", "Low"],
                   ["Zone outage in cloud region", "High", "Active-active across two zones; RPO 5 minutes, RTO 30 minutes; game days", "Low"],
                   ["Payment fraud via portal", "Medium", "Device fingerprinting, velocity limits, tokenised payments, PCI DSS scope reduction", "Low"],
                   ["Privacy breach under DPDP Act", "High", "Consent ledger, field-level encryption, DPIA, 1-hour internal escalation, 72-hour regulator notice process", "Low"],
                   ["Supply-chain compromise", "Medium", "SBOM per release, signed images, vendor assessments, dependency pinning", "Medium"]],
                  [0.26, 0.10, 0.52, 0.12]),
                H("Business continuity"),
                "The disaster recovery plan is tested twice a year with the Board's participation. Backups are encrypted, "
                "replicated across zones and retained for 35 days online and 7 years archived. A documented incident "
                "response plan commits Apex to notify the Board within 1 hour of confirmed personal-data compromise and "
                "to provide a root-cause report within 5 working days.",
            ]),
            ("8. Support Model and Service Level Agreement", [
                "Support is provided 24x7 for Priority 1 incidents with a 30-minute response time and 4-hour "
                "resolution target; Priority 2 within 2 hours. A named service manager runs monthly service reviews.",
                T([["Priority", "Definition", "Response", "Resolution target", "Update frequency"],
                   ["P1 Critical", "Billing or payments unavailable, data breach", "30 minutes", "4 hours", "Every 30 minutes"],
                   ["P2 High", "Major function degraded, workaround exists", "2 hours", "8 hours", "Every 2 hours"],
                   ["P3 Medium", "Minor function impaired", "1 business day", "5 business days", "Daily"],
                   ["P4 Low", "Question or cosmetic issue", "2 business days", "Next release", "Weekly"]],
                  [0.14, 0.34, 0.16, 0.18, 0.18]),
                "Platform availability commitment is 99.95 percent per month, measured at the API gateway, excluding "
                "agreed maintenance windows (maximum 4 hours per month, Sundays 01:00-05:00). Service credits are 5 "
                "percent of the monthly subscription for each 0.1 percent below target, capped at 25 percent.",
                H("Support organisation"),
                "Tier 1 is a 24x7 service desk in Pune; Tier 2 is the application support team (9 engineers across three "
                "shifts); Tier 3 is the product engineering team with on-call rotation. During hypercare, 4 engineers "
                "are on site at Meridian HQ and zone offices. A named service manager chairs monthly service reviews and "
                "a quarterly roadmap review.",
            ]),
            ("9. Relevant Experience and References", [
                "Apex has completed 6 utility billing implementations in the last 8 years, including two water utilities. "
                "Our utilities practice has 85 staff and a retention rate of 91 percent over the last three years.",
                T([["Reference client (fictional)", "Scope", "Year"],
                   ["Sundara City Water Corporation", "Billing and CRM for 800,000 connections", "2024"],
                   ["Eastern Grid Power Distribution", "Billing platform and SAP integration", "2022"]],
                  [0.40, 0.45, 0.15]),
                H("Reference outcomes"),
                T([["Reference", "Outcome", "Contact"],
                   ["Sundara City Water Corporation", "On-time go-live in 38 weeks; billing exceptions reduced from 5.1 to 1.2 percent; 99.96 percent availability in first year",
                    "Chief Information Officer; consent given for call"],
                   ["Eastern Grid Power Distribution", "SAP S/4HANA integration live in 31 weeks; bill run time cut from 11 hours to 2 hours 40 minutes",
                    "Head of Revenue Systems; consent given for call"]],
                  [0.28, 0.50, 0.22]),
            ]),
            ("10. Assumptions and Exclusions", [
                H("Assumptions"),
                B("The Board provides SAP S/4HANA and MDM test environments by week 9, with technical contacts available within 2 working days.",
                  "Tariff rules and billing policies are frozen at design sign-off (week 8). Later changes follow change control.",
                  "The Board nominates a single product owner with decision authority, and subject-matter experts for 2 days per week during design and UAT.",
                  "Legacy data extracts are provided in agreed formats by week 12; data quality issues beyond 2 cleansing cycles are a change request.",
                  "Cloud hosting is in an Indian region of Apex's chosen provider; the Board has no preference for a specific provider."),
                H("Exclusions"),
                B("Replacement or upgrade of the Board's SAP S/4HANA and MDM systems.",
                  "Meter hardware, network connectivity upgrades at zone offices and end-user devices.",
                  "Paper bill printing and postal services; SMS, email and WhatsApp message charges (billed at actuals by the gateway providers).",
                  "GST and any statutory levies, which are payable in addition to the quoted prices.",
                  "Digitisation of paper records older than the 14-year legacy system history."),
            ]),
            ("11. Appendices", [
                H("Appendix A: Key staff summaries"),
                T([["Name (fictional)", "Role", "Experience"],
                   ["Rohan Deshpande", "Delivery director", "22 years in enterprise delivery; led Sundara City Water programme (800,000 connections); PMP, ITIL 4"],
                   ["Meera Iyer", "Project manager", "15 years; delivered 4 utility billing programmes; PMP and PRINCE2 Practitioner"],
                   ["Dr. Kabir Anand", "Lead solution architect", "19 years; designed Kafka-based billing platforms; TOGAF 9 certified; ex-SAP integration lead"],
                   ["Latha Ramaswamy", "Security architect", "14 years; CISSP and CISM; led ISO 27001 and SOC 2 Type II audits for Apex"],
                   ["Imran Sheikh", "QA lead", "12 years; performance engineering of 3 million account billing runs; ISTQB Advanced"]],
                  [0.22, 0.20, 0.58]),
                H("Appendix B: Glossary"),
                T([["Term", "Meaning"],
                   ["AMI", "Advanced metering infrastructure, the smart meter network"],
                   ["MDM", "Meter data management system holding validated meter reads"],
                   ["RPO / RTO", "Recovery point objective (data loss tolerance) and recovery time objective (restoration time)"],
                   ["VAPT", "Vulnerability assessment and penetration testing"],
                   ["DPDP Act", "Digital Personal Data Protection Act, India"],
                   ["SIEM", "Security information and event management"],
                   ["UAT", "User acceptance testing by the Board"]],
                  [0.2, 0.8]),
                H("Appendix C: Compliance statement"),
                "Apex confirms that this proposal complies with all mandatory requirements in RFP MRWB-2026-014 "
                "and that no deviations are taken. Certificates and the SOC 2 Type II report summary will be shared "
                "with the Board's evaluation committee on request under NDA.",
            ]),
        ],
    },
    # ------------------------------------------------------------ BRIGHTPATH: cheapest, fastest, weak compliance
    {
        "name": "BrightPath Tech", "file": "BrightPath_Tech_Proposal.pdf", "date": "2026-10-18", "accent": "#E8590C",
        "cover": [["Item", "Detail"],
                  ["Bidder", "BrightPath Tech LLP, Hyderabad, India"],
                  ["Proposed solution", "QuickBill low-code billing platform with customer portal"],
                  ["Contract duration", "16 weeks"],
                  ["Total 3-year cost", "INR 6.04 Cr (indicative)"]],
        "sections": [
            ("1. Executive Summary and Understanding of the Requirement", [
                "BrightPath Tech is a fast-growing digital agency offering the most cost-effective route to a modern "
                "billing and customer service experience for the Meridian Regional Water Board. We can deliver a working "
                "platform in just 16 weeks at a total three-year cost under INR 7 crore.",
                "We are a young company founded in 2022 and bring energy, speed and modern tooling to every project. "
                "Our team of 28 people is based in Hyderabad and works closely with clients using weekly demonstrations.",
                "We understand the Board wants a new billing system and a customer portal so customers can pay bills "
                "online and raise complaints. We also understand that the Board would like to move away from its older "
                "system and offer a better experience to customers. We have worked with many clients who wanted to modernise "
                "quickly and we know how to keep projects simple.",
                "Our approach is to start with what the Board already has, keep changes small and get something live "
                "as soon as possible. Additional features can be added after go-live as the Board's needs become clearer.",
                B("Lowest price among the options the Board is likely to receive.",
                  "Fastest delivery: 16 weeks from contract signature to go-live.",
                  "Modern, mobile-friendly customer experience.",
                  "Friendly, flexible team that welcomes feedback."),
            ]),
            ("2. Proposed Solution and Architecture", [
                "We will customise our low-code platform, QuickBill, which provides billing, payments and a simple "
                "customer portal. The portal will be mobile friendly. QuickBill runs on a single cloud server which can "
                "be upgraded if more capacity is needed.",
                "QuickBill was first released in 2024 and is used by two small clients for subscription billing. The "
                "platform lets our developers build screens and billing rules quickly without writing much code. For "
                "the Board we will configure water tariffs, bill generation and online payment.",
                T([["Component", "Description"],
                   ["Billing module", "Generates monthly bills from meter readings using configured tariff slabs"],
                   ["Customer portal", "Web portal where customers can view bills, pay online and submit complaints"],
                   ["Payments", "Integration with a standard online payment gateway"],
                   ["Admin screens", "Basic screens for staff to look up accounts and update details"],
                   ["Hosting", "Single cloud server in India with daily backups"]],
                  [0.25, 0.75]),
                "The platform can handle the Board's customers. Exact performance figures will be measured during testing. "
                "If the number of users grows, the server size can be increased.",
                H("Customer experience"),
                "The portal will have a clean, modern look and will work on phones and desktops. Customers can see "
                "their latest bill, download a PDF copy, pay online and report an issue. Language support will be "
                "decided with the Board later.",
            ]),
            ("3. Integration Approach", [
                "Integration with the finance system will be done through file exports. Other integrations will be "
                "discussed after contract award.",
                "For meter readings, the Board's team can send us a file of readings every month which we will upload "
                "into QuickBill. We may look at connecting directly to the meter system in a later phase.",
                T([["System", "Approach"],
                   ["Finance system (SAP)", "Monthly file export"],
                   ["Meter data system", "To be discussed after contract award"],
                   ["Payment gateway", "Standard plug-in"]],
                  [0.35, 0.65]),
            ]),
            ("4. Implementation Approach", [
                "We use an agile approach with weekly demos to keep things moving quickly. Requirements will be gathered "
                "in the first two weeks through a small number of workshops with the Board's team. The developers will then "
                "configure and customise QuickBill in short cycles, showing progress every week.",
                B("Weekly demonstration call with the Board's project contact.",
                  "Requirements captured as simple user stories in a shared tracker.",
                  "Issues fixed as they are found; no heavy documentation.",
                  "A short handover note at the end of the project."),
                "Team: 1 project lead and 4 developers. Testing will be done by the developers. Data migration will "
                "be handled by the Board's IT team with our guidance.",
            ]),
            ("5. Timeline, Team Structure and Milestones", [
                T([["Stage", "Weeks"],
                   ["Setup and configuration", "1-4"],
                   ["Customisation", "5-11"],
                   ["Testing", "12-14"],
                   ["Go-live", "15-16"]],
                  [0.6, 0.4]),
                "The timeline is aggressive but achievable because the team is small and decisions can be made quickly. "
                "Milestones will be shared with the Board during the project. If the Board needs changes to the plan, "
                "we will adjust as we go.",
                T([["Role", "Number"],
                   ["Project lead", "1"],
                   ["Developers", "4"]],
                  [0.6, 0.4]),
            ]),
            ("6. Commercial Proposal and Price Table", [
                T([["Item", "Price (INR)"],
                   ["Implementation and customisation", "2,40,00,000"],
                   ["QuickBill licence (3 years)", "3,60,00,000"],
                   ["Training (2 sessions)", "4,00,000"],
                   ["Total 3-year cost", "6,04,00,000"]],
                  [0.6, 0.4]),
                "Prices are indicative and may change after detailed requirements are confirmed. Hosting costs are "
                "not included.",
                "Payment terms: 50 percent on contract signature and 50 percent on go-live. The licence is invoiced "
                "annually in advance. Additional work requested by the Board will be quoted separately.",
                "We believe this is the best value offer for the Board because we keep our overheads low and use our "
                "own platform rather than expensive third-party products.",
            ]),
            ("7. Security, Compliance and Risk Controls", [
                "We take security seriously. Data is protected by passwords and the cloud provider's standard firewall. "
                "We are planning to begin ISO 27001 certification next year. We will follow applicable data protection "
                "laws.",
                T([["Area", "Our approach"],
                   ["Access", "User names and passwords"],
                   ["Network", "Cloud provider's standard firewall"],
                   ["Certification", "ISO 27001 planned"],
                   ["Data protection", "We will follow applicable laws"]],
                  [0.3, 0.7]),
                "Risks will be managed by the project lead as they arise.",
            ]),
            ("8. Support Model and Service Levels", [
                "Support is available Monday to Friday, 9 am to 6 pm, by email. We aim to respond within one business day.",
                "Urgent problems can be raised by phone to the project lead during working hours. Fixes will be "
                "provided as quickly as possible. We do not currently offer a formal service level agreement, but we "
                "can discuss this if needed.",
            ]),
            ("9. Relevant Experience and References", [
                "We have delivered 3 web portals for retail and education clients. This would be our first utility "
                "billing project. References can be provided on request.",
                T([["Past project (fictional)", "Type", "Year"],
                   ["BookNest Retail", "E-commerce portal", "2023"],
                   ["Learnwell Academy", "Student portal", "2024"],
                   ["Fresh Basket Stores", "Online ordering portal", "2025"]],
                  [0.4, 0.4, 0.2]),
            ]),
            ("10. Assumptions and Exclusions", [
                B("The Board provides clear requirements in the first two weeks.",
                  "The Board's IT team performs data migration and provides test data.",
                  "Hosting costs, SMS charges and payment gateway fees are not included.",
                  "Any integration other than the finance file export is out of scope until agreed.",
                  "Prices exclude GST."),
            ]),
            ("11. Appendices", [
                H("Appendix A: Team"),
                T([["Name (fictional)", "Role", "Background"],
                   ["Arjun Rao", "Project lead", "8 years in web projects; founder of BrightPath"],
                   ["Developers (4)", "Developers", "Web and low-code developers with 2-5 years of experience"]],
                  [0.25, 0.2, 0.55]),
                H("Appendix B: Glossary"),
                T([["Term", "Meaning"],
                   ["Low-code", "A way of building software using configuration with little coding"],
                   ["Portal", "Website where customers log in"],
                   ["ISO 27001", "An international information security standard"]],
                  [0.25, 0.75]),
            ]),
        ],
    },
    # ------------------------------------------------------------ NEXAWORKS: balanced; best implementation + support
    {
        "name": "NexaWorks", "file": "NexaWorks_Proposal.pdf", "date": "2026-10-20", "accent": "#0F766E",
        "cover": [["Item", "Detail"],
                  ["Bidder", "NexaWorks Technologies Pvt. Ltd., Bengaluru, India"],
                  ["Proposed solution", "NexaBill configurable utility billing product with managed cloud hosting"],
                  ["Contract duration", "32 weeks in five gated phases"],
                  ["Total 3-year cost", "INR 10.40 Cr (fixed-price implementation), excludes GST"],
                  ["Certifications", "ISO 27001 (2023); SOC 2 Type I completed, Type II in progress"],
                  ["Support", "Dedicated 24x7 utility service desk"]],
        "sections": [
            ("1. Executive Summary and Understanding of the Requirement", [
                "NexaWorks proposes a balanced, low-risk modernisation of the Meridian Regional Water Board's billing "
                "and customer service operations. Our proposal is built around a proven delivery method, a realistic "
                "32-week plan and a support model designed for 24x7 utility operations.",
                "We focus on predictable delivery: in our last 9 utility programmes, 8 went live on the planned date.",
                "The Board must replace its legacy billing system, unify customer contact channels, integrate with "
                "SAP S/4HANA and the AMI meter data management system, migrate 14 years of customer history and "
                "reduce billing exceptions while maintaining DPDP Act compliance.",
                "Having reviewed the RFP and the data room, we believe the principal risks are not technical novelty "
                "but sequencing and coordination: environment readiness for SAP and MDM, the quality of legacy data, "
                "and adoption by 11 zone offices. Our plan is therefore designed around gates, early risk retirement and "
                "a change-management workstream that runs in parallel with the build.",
                H("What the Board gets"),
                B("A five-gate delivery plan with written entry and exit criteria, so the Board can see progress and stop or adjust at each gate.",
                  "A product that is configured, not custom coded: 85 percent of required tariff and workflow behaviour is available out of the box.",
                  "A 24x7 utility service desk with a 15-minute Priority 1 response and 99.9 percent availability commitment.",
                  "Fixed-price implementation with milestone payments tied to gates.",
                  "Security baseline: ISO 27001 certified, AES-256 encryption, MFA, India-only data residency."),
                H("Summary of key commitments"),
                T([["Area", "Commitment"],
                   ["Duration", "32 weeks, go-live in week 29, hypercare to week 32"],
                   ["Price", "INR 10.40 Cr over 3 years, fixed-price implementation"],
                   ["Team", "16 FTE at peak, named programme manager and cutover manager"],
                   ["Support", "24x7, P1 response 15 minutes, resolution 4 hours"],
                   ["Availability", "99.9 percent monthly with service credits"]],
                  [0.25, 0.75]),
            ]),
            ("2. Proposed Solution and Architecture", [
                "We will implement our configurable utility billing product, NexaBill, on a managed cloud platform hosted in India, "
                "with a hot standby site. The platform exposes REST APIs and uses a message queue for asynchronous "
                "integration with SAP S/4HANA (finance postings) and MDM (meter reads). It is sized for 1.5 million "
                "connections and scales horizontally. A customer portal, mobile app and agent desktop share one customer record.",
                T([["Capability", "How it is delivered", "Sizing / target"],
                   ["Billing and rating", "Configurable tariff engine; slab, seasonal and subsidy tariffs", "1.5 million connections; billing run under 5 hours"],
                   ["Customer portal and mobile app", "Responsive portal, Android and iOS app, UPI payments", "1,500 concurrent users"],
                   ["Agent desktop", "Single customer view across calls, email, walk-in and field requests", "320 agents"],
                   ["Field requests", "Work orders to field crews with status updates to customers", "Integrated with notifications"],
                   ["Hosting", "Primary site plus hot standby in a second Indian data centre", "RPO 15 minutes, RTO 2 hours"]],
                  [0.22, 0.46, 0.32]),
                H("Deployment view"),
                "The production environment runs on managed Kubernetes with a database cluster and message queue "
                "replicated to the standby site. Non-production environments (development, test, UAT, training) are "
                "provisioned in week 3 and shut down outside working hours to save cost. A performance test environment "
                "mirrors production at 50 percent scale.",
                H("Why configuration over customisation"),
                "NexaBill has been implemented at 9 utilities. Because the tariff engine and workflow designer are "
                "configuration based, the Board can adjust tariff policy and notification rules without code releases. "
                "Where gaps remain they are recorded in a fit-gap register during Gate 2 and priced inside the fixed fee.",
            ]),
            ("3. Integration Approach", [
                "Integration with SAP S/4HANA and the AMI MDM is covered by named specifications delivered in Gate 2.",
                T([["Interface", "Approach", "Test evidence"],
                   ["SAP S/4HANA finance", "Asynchronous postings through the message queue using standard BAPIs and IDocs; nightly reconciliation report",
                    "End-to-end test with 3 months of anonymised postings"],
                   ["AMI MDM", "Scheduled and on-demand read retrieval through REST and file adapters; estimation rules for missing reads",
                    "Reads for 100,000 meters replayed in SIT"],
                   ["Payment gateways", "UPI and card via two certified gateways with fail-over",
                    "Gateway test certification before UAT"],
                   ["Messaging", "SMS and email gateway adapters with delivery tracking", "Delivery receipts reconciled in UAT"]],
                  [0.22, 0.50, 0.28]),
                "An integration lead is assigned from week 1. Interface specifications are signed jointly with the Board's "
                "SAP and MDM owners by end of Gate 2 (week 10), and integration tests are a mandatory exit criterion "
                "for Gate 3.",
            ]),
            ("4. Implementation Approach", [
                "We follow our five-gate delivery method. Every gate has documented entry and exit criteria and requires "
                "joint sign-off by the Board.",
                T([["Gate / phase", "Entry criteria", "Exit criteria", "Sign-off"],
                   ["G1 Mobilise and discover", "Contract signed, sponsor named", "Charter, governance plan, risk register baseline", "Board sponsor, NexaWorks programme manager"],
                   ["G2 Design", "G1 complete, workshops scheduled", "Signed solution design, integration specs, migration strategy", "Board architecture review"],
                   ["G3 Build and integrate", "Design signed, environments ready", "4 sprints complete; SAP and MDM integration tests passed", "Board PMO"],
                   ["G4 Migrate and test", "G3 complete, mock data loaded", "3 mock migrations; SIT, UAT and performance tests passed", "Board steering committee"],
                   ["G5 Cutover and hypercare", "Go-live readiness checklist green", "Go-live, 4 weeks hypercare, handover to support", "Board sponsor"]],
                  [0.20, 0.24, 0.34, 0.22]),
                H("Data migration"),
                "A dedicated data migration lead owns profiling, cleansing, mapping and reconciliation. Cleansing "
                "sprint runs in weeks 8-12; three mock migrations (weeks 17, 22, 26) each produce a reconciliation "
                "report signed by the Board's finance team. Cutover is rehearsed twice.",
                H("Change and training"),
                "A change and training lead works with 11 zone champions. The plan includes 25 classroom sessions, "
                "quick-reference guides, a training sandbox and floor-walking support for 4 weeks after go-live.",
            ]),
            ("5. Timeline, Team Structure and Milestones", [
                T([["Gate / phase", "Weeks", "Milestone and acceptance criteria"],
                   ["G1 Mobilise and discover", "1-4", "Project charter, governance plan, risk register baseline"],
                   ["G2 Design", "5-10", "Signed solution design, integration specs, data migration strategy"],
                   ["G3 Build and integrate (4 sprints)", "11-20", "SAP and MDM integration tests passed"],
                   ["G4 Migrate and test", "17-28", "3 mock migrations; SIT, UAT and performance tests passed"],
                   ["G5 Cutover and hypercare", "29-32", "Go-live, 4 weeks hypercare, handover to support"]],
                  [0.30, 0.10, 0.60]),
                "Team structure (16 FTE at peak): programme manager, project manager, business analyst lead, 2 "
                "solution architects, 6 developers, 2 testers, data migration lead, change and training lead, and a "
                "dedicated cutover manager. A steering committee meets monthly and the project board weekly.",
                T([["Role", "FTE", "Gate involvement"],
                   ["Programme manager", "0.5", "All gates; owns steering committee"],
                   ["Project manager", "1.0", "All gates; weekly project board"],
                   ["Business analyst lead", "1.0", "G1-G4"],
                   ["Solution architects", "2.0", "G2-G4"],
                   ["Developers", "6.0", "G3-G4, support in G5"],
                   ["Testers", "2.0", "G3-G5"],
                   ["Data migration lead", "1.0", "G2-G5"],
                   ["Change and training lead", "1.0", "G2-G5"],
                   ["Cutover manager", "0.5 (1.0 in G5)", "G4-G5"]],
                  [0.40, 0.20, 0.40]),
                H("Risk register"),
                "Risk plan: top risks include SAP test environment availability (mitigation: early environment "
                "booking and service virtualisation), data quality in legacy records (mitigation: data cleansing "
                "sprint in weeks 8-12) and staff adoption (mitigation: change champions in every zone office).",
                T([["ID", "Risk", "Probability / impact", "Mitigation", "Owner"],
                   ["R1", "SAP test environment delayed", "Medium / High", "Book in week 1; service virtualisation; escalate at project board if not ready by week 9", "Integration lead"],
                   ["R2", "Poor legacy data quality", "High / High", "Cleansing sprint weeks 8-12; 3 mock migrations with reconciliation", "Data migration lead"],
                   ["R3", "Staff adoption in zone offices", "Medium / Medium", "Champion network, 25 classroom sessions, floor-walkers", "Change lead"],
                   ["R4", "Scope growth after design", "Medium / High", "Change control board; scope freeze at G2 exit", "Project manager"],
                   ["R5", "Key staff loss", "Low / Medium", "Named deputies for every lead role; handover documentation", "Programme manager"]],
                  [0.07, 0.24, 0.17, 0.38, 0.14]),
            ]),
            ("6. Commercial Proposal and Price Table", [
                T([["Item", "Price (INR)", "Notes"],
                   ["Implementation services (fixed price)", "4,90,00,000", "Paid against the five gates"],
                   ["Subscription and hosting, Year 1", "1,70,00,000", "Includes DR site"],
                   ["Subscription and hosting, Year 2", "1,70,00,000", ""],
                   ["Subscription and hosting, Year 3", "1,70,00,000", "No uplift"],
                   ["Data migration, training and change", "40,00,000", "Includes 25 classroom sessions"],
                   ["Total 3-year cost", "10,40,00,000", "Excludes GST"]],
                  [0.40, 0.20, 0.40]),
                "Assumptions: Board subject-matter experts available 3 days per week; change requests at INR 15,000 "
                "per person-day; prices valid for 120 days.",
                H("Payment against gates"),
                T([["Gate", "Payment share", "Amount (INR)"],
                   ["G1 complete", "10 percent", "49,00,000"],
                   ["G2 complete", "20 percent", "98,00,000"],
                   ["G3 complete", "30 percent", "1,47,00,000"],
                   ["G4 complete", "25 percent", "1,22,50,000"],
                   ["G5 complete", "15 percent", "73,50,000"]],
                  [0.4, 0.3, 0.3]),
                "Subscription is invoiced quarterly in advance from go-live. Connections above 1.5 million are charged "
                "at INR 11 per connection per month. There is no annual uplift during the 3-year term.",
            ]),
            ("7. Security, Compliance and Risk Controls", [
                B("ISO 27001 certified (2023); SOC 2 Type I completed, Type II audit in progress.",
                  "Encryption of data at rest (AES-256) and in transit (TLS 1.2+); MFA and role-based access control.",
                  "Audit trail for every billing adjustment; logs retained for 5 years.",
                  "DPDP Act compliant consent capture; all data stored in India.",
                  "Annual third-party VAPT; incident response within 2 hours."),
                T([["Risk", "Control", "Owner"],
                   ["Data breach", "Encryption, MFA, role-based access, quarterly access recertification", "NexaWorks CISO"],
                   ["Billing adjustment fraud", "Maker-checker on adjustments, full audit trail, exception report to Board finance", "Project manager / Board finance"],
                   ["Site failure", "Hot standby site, RPO 15 minutes, RTO 2 hours, annual failover test", "Operations manager"],
                   ["Privacy non-compliance", "Consent capture, India residency, data subject request workflow", "Data protection officer"]],
                  [0.25, 0.52, 0.23]),
                "SOC 2 Type II is expected to complete in Q2 2027; we will share the Type I report and the audit "
                "plan on request.",
            ]),
            ("8. Support Model and Service Level Agreement", [
                "Our support model is a dedicated 24x7 utility service desk with a named account manager and customer "
                "success lead. SLA: Priority 1 response 15 minutes, resolution 4 hours; Priority 2 response 1 hour, "
                "resolution 8 hours; 99.9 percent monthly availability with service credits. Quarterly roadmap reviews "
                "and a release plan are included.",
                T([["Priority", "Response", "Resolution", "Channel"],
                   ["P1 Critical", "15 minutes", "4 hours", "Phone, 24x7"],
                   ["P2 High", "1 hour", "8 hours", "Phone and portal, 24x7"],
                   ["P3 Medium", "4 business hours", "3 business days", "Portal"],
                   ["P4 Low", "1 business day", "Next release", "Portal"]],
                  [0.22, 0.26, 0.26, 0.26]),
                B("Service credits: 5 percent of monthly fee when availability falls below 99.9 percent, 10 percent below 99.5 percent.",
                  "Named account manager and customer success lead; monthly service report; quarterly roadmap review.",
                  "Release management: one minor release per quarter with 14 days' notice and a regression test report.",
                  "Hypercare: 4 weeks of on-site support with daily stand-up and a defect burn-down."),
            ]),
            ("9. Relevant Experience and References", [
                "We have completed 9 utility implementations in 7 years.",
                T([["Reference client (fictional)", "Scope", "Year"],
                   ["Lakeview Municipal Water", "Billing, CRM and portal, 650,000 connections", "2025"],
                   ["Coastal Gas Distribution Ltd", "Billing and SAP integration", "2024"],
                   ["Hillstate Water Authority", "Customer portal and agent desktop", "2023"]],
                  [0.36, 0.48, 0.16]),
                "Lakeview Municipal Water went live on the planned date after a 30-week programme using the same "
                "five-gate method. Coastal Gas went live one week late due to a client environment delay.",
            ]),
            ("10. Assumptions and Exclusions", [
                H("Assumptions"),
                B("Board subject-matter experts are available 3 days per week.",
                  "SAP and MDM test environments are available by week 9.",
                  "Board approvers sign off each gate within 5 working days.",
                  "Prices are valid for 120 days from submission."),
                H("Exclusions"),
                B("GST and statutory levies.",
                  "Third-party message charges and payment gateway fees.",
                  "Hardware and network upgrades at Board offices.",
                  "Upgrades to the Board's SAP or MDM systems."),
            ]),
            ("11. Appendices", [
                H("Appendix A: Key staff"),
                T([["Name (fictional)", "Role", "Experience"],
                   ["Neha Kulkarni", "Programme manager", "17 years; led 5 utility programmes; PMP"],
                   ["Vikram Joshi", "Cutover manager", "13 years; 11 production cutovers, including Lakeview"],
                   ["Anita Das", "Data migration lead", "12 years; migrated over 40 million billing records"]],
                  [0.25, 0.25, 0.50]),
                H("Appendix B: Glossary"),
                T([["Term", "Meaning"],
                   ["Gate", "A formal checkpoint with exit criteria and Board sign-off"],
                   ["SIT", "System integration testing"],
                   ["Hypercare", "Intensive support after go-live"]],
                  [0.25, 0.75]),
            ]),
        ],
    },
    # ------------------------------------------------------------ ORBIT: strong experience, vague integration
    {
        "name": "Orbit Digital", "file": "Orbit_Digital_Proposal.pdf", "date": "2026-10-22", "accent": "#6D28D9",
        "cover": [["Item", "Detail"],
                  ["Bidder", "Orbit Digital Services Ltd., Bengaluru, India"],
                  ["Proposed solution", "Orbit UtilityOne billing and customer engagement suite"],
                  ["Duration", "Approximately 36 weeks"],
                  ["Estimated 3-year cost", "INR 10.85 Cr (time and materials estimate)"],
                  ["Experience", "22 billing implementations, 14 utility clients"]],
        "sections": [
            ("1. Executive Summary and Understanding of the Requirement", [
                "Orbit Digital has served the utilities sector for 18 years and has delivered more billing "
                "transformations than any other firm in the region. We bring an experienced team, strong client "
                "relationships and a portfolio of 14 utility clients who can speak to our results.",
                "The Board wishes to modernise billing and customer service, improve customer satisfaction and reduce "
                "operational cost. We have seen these challenges many times before.",
                "Our long track record means we understand how utility organisations work, how regulators think and "
                "how to keep customers informed during change. We have worked with water, electricity and gas "
                "utilities of all sizes, and we know that every transformation has its own character.",
                B("18 years in the utilities sector.",
                  "22 completed billing implementations, including water utilities of a similar scale.",
                  "5 reference clients who have agreed to be contacted.",
                  "A mature product, UtilityOne, which has been refined across many deployments.",
                  "A Bengaluru-based service centre providing 24x7 coverage for critical incidents."),
                H("Our experience in numbers"),
                T([["Measure", "Value"],
                   ["Years in utilities", "18"],
                   ["Billing implementations completed", "22"],
                   ["Utility clients served", "14"],
                   ["Largest deployment", "1.1 million connections (Northbank Water Utility)"],
                   ["Staff in utilities practice", "120"]],
                  [0.5, 0.5]),
            ]),
            ("2. Proposed Solution and Architecture", [
                "We will deploy Orbit UtilityOne, our billing and customer engagement suite, hosted in a cloud region in India. "
                "UtilityOne includes billing, payments, a customer portal and a contact-centre module.",
                "UtilityOne is a mature product that has evolved over more than a decade. It is multi-tenant in design "
                "but will be deployed as a dedicated instance for the Board. The suite is organised into modules which "
                "can be switched on as the Board is ready.",
                T([["Module", "Description"],
                   ["Billing", "Metering-to-cash processing with configurable tariffs"],
                   ["Payments", "Online, counter and agent payments with reconciliation"],
                   ["Customer portal", "Self-service for bills, payments and requests"],
                   ["Contact centre", "Case management and call handling"],
                   ["Reporting", "Standard operational and management reports"]],
                  [0.25, 0.75]),
                "Hosting will be in a cloud region in India with backups. Detailed sizing, resilience design and "
                "performance targets will be agreed during design. Scalability will be assessed during design.",
            ]),
            ("3. Integration Approach", [
                "Integration approach: integrations with SAP and the meter data management system will be determined "
                "during the discovery phase once we understand the Board's landscape. Our team has integrated with "
                "many systems in the past and we are confident this will not be an issue. Scalability will be assessed "
                "during design.",
                T([["System", "Approach", "Status"],
                   ["SAP S/4HANA", "Method to be confirmed in discovery", "To be confirmed"],
                   ["Meter data management", "Interfaces to be defined with the Board's team", "To be confirmed"],
                   ["Payment gateways", "Standard gateway adapters, selection with the Board", "To be confirmed"],
                   ["Other systems", "Identified during discovery", "To be confirmed"]],
                  [0.30, 0.48, 0.22]),
                "Specific protocols, data volumes and test approaches will be to be confirmed in discovery. Because "
                "the integration scope is not yet known, effort and cost for integrations are included only as an "
                "allowance and may change.",
            ]),
            ("4. Implementation Approach", [
                "Our methodology has been refined over 18 years. The programme will take approximately 36 weeks.",
                "The methodology is organised into four phases, each led by an experienced consultant. Discovery "
                "establishes the detail of what is needed; configuration and integration builds it; testing checks it; "
                "deployment brings it into live use. Our consultants will work closely with the Board's team throughout "
                "and adapt the approach to the Board's culture.",
                B("Discovery workshops with each business area.",
                  "Iterative configuration with regular reviews.",
                  "Testing with the Board's users before go-live.",
                  "Deployment support and a handover to our service centre."),
                H("Data migration and training"),
                "Data migration approach will be defined in discovery. Training will be delivered to the Board's staff "
                "before go-live; the number and format of sessions will be agreed in discovery.",
            ]),
            ("5. Timeline, Team Structure and Milestones", [
                T([["Phase", "Approximate duration"],
                   ["Discovery", "8 weeks"],
                   ["Configuration and integration", "16 weeks"],
                   ["Testing", "8 weeks"],
                   ["Deployment", "4 weeks"]],
                  [0.6, 0.4]),
                "Team: an engagement partner, a project manager and a team of consultants whose size will be confirmed "
                "after discovery. Detailed milestones will be agreed after discovery.",
                T([["Role", "Number"],
                   ["Engagement partner", "1"],
                   ["Project manager", "1"],
                   ["Consultants", "To be confirmed after discovery"]],
                  [0.5, 0.5]),
            ]),
            ("6. Commercial Proposal and Price Table", [
                T([["Item", "Price (INR)"],
                   ["Implementation services (time and materials estimate)", "5,20,00,000"],
                   ["UtilityOne licence and hosting, 3 years", "5,40,00,000"],
                   ["Training", "25,00,000"],
                   ["Estimated total 3-year cost", "10,85,00,000"]],
                  [0.65, 0.35]),
                "Implementation is estimated on a time-and-materials basis at a blended rate of INR 16,000 per "
                "person-day; the final figure depends on integration scope confirmed in discovery. Licence prices "
                "increase in line with inflation each year.",
                "The estimate assumes about 3,250 person-days. Invoices for implementation will be raised monthly on "
                "actual time spent. Orbit will notify the Board if the estimate is likely to be exceeded. Any "
                "additional work beyond the estimate will be charged at the same rate.",
                "Note that the total above is an estimate and not a fixed or capped price.",
            ]),
            ("7. Security, Compliance and Risk Controls", [
                "Orbit Digital is ISO 27001 certified. UtilityOne supports role-based access control, encryption of "
                "data in transit and at rest, and audit logging. We comply with Indian data protection regulations. "
                "Penetration testing is performed annually.",
                T([["Risk", "Mitigation"],
                   ["Integration scope larger than expected", "Review in discovery; adjust estimate"],
                   ["Schedule slippage", "Regular status reviews"],
                   ["Data protection", "Comply with applicable regulations"]],
                  [0.4, 0.6]),
            ]),
            ("8. Support Model and Service Level Agreement", [
                "Support is provided through our Bengaluru service centre with 24x7 coverage for critical incidents, "
                "a named account manager and an escalation path to the engagement partner. Priority 1 response within "
                "1 hour.",
                T([["Priority", "Response"],
                   ["P1 Critical", "Within 1 hour, 24x7"],
                   ["P2 High", "Within 4 business hours"],
                   ["P3 and P4", "Within 2 business days"]],
                  [0.5, 0.5]),
                "Resolution targets and availability commitments will be set out in the support agreement.",
            ]),
            ("9. Relevant Experience and References", [
                "Experience: 18 years in utilities, 14 utility clients and 22 completed billing implementations, "
                "including water, electricity and gas utilities.",
                T([["Reference client (fictional)", "Scope", "Year"],
                   ["Northbank Water Utility", "UtilityOne billing, 1.1 million connections", "2025"],
                   ["Riverside Electricity Board", "Billing and contact centre", "2024"],
                   ["Greenfield Gas Company", "Billing replacement", "2023"],
                   ["Central Plains Water Trust", "Billing and customer portal", "2022"],
                   ["Metro Water and Sewerage Board", "Billing upgrade", "2021"]],
                  [0.36, 0.48, 0.16]),
                "All references have agreed to be contacted by the Board.",
                H("Selected project highlights"),
                B("Northbank Water Utility: replaced a 20-year-old billing system for 1.1 million connections and migrated customer records to UtilityOne.",
                  "Riverside Electricity Board: implemented billing and a contact-centre module for a regional electricity board.",
                  "Greenfield Gas Company: replaced billing within the planned period.",
                  "Central Plains Water Trust and Metro Water and Sewerage Board: billing and portal upgrades completed for water utilities."),
            ]),
            ("10. Assumptions and Exclusions", [
                B("Integration scope and effort will be confirmed in discovery and may change the estimate.",
                  "The Board provides timely access to its SAP and MDM teams and systems.",
                  "Team size and milestones will be agreed after discovery.",
                  "Prices exclude GST, hosting growth beyond the standard configuration and third-party charges.",
                  "Licence prices increase annually in line with inflation."),
            ]),
            ("11. Appendices", [
                H("Appendix A: Key staff"),
                T([["Name (fictional)", "Role", "Experience"],
                   ["Suresh Menon", "Engagement partner", "24 years in utilities consulting; led Northbank programme"],
                   ["Divya Narayan", "Project manager", "14 years of billing project management"]],
                  [0.25, 0.25, 0.50]),
                H("Appendix B: Glossary"),
                T([["Term", "Meaning"],
                   ["T&M", "Time and materials, charging for actual effort"],
                   ["MDM", "Meter data management system"],
                   ["Discovery", "Initial phase to establish detailed requirements"]],
                  [0.25, 0.75]),
            ]),
        ],
    },
]


def merged_sections(supplier):
    extra = EXTRA.get(supplier["name"], {})
    out = []
    for sec in supplier["sections"]:
        if sec != "PAGEBREAK" and sec[0].split(".")[0] in extra:
            sec = (sec[0], list(sec[1]) + extra[sec[0].split(".")[0]])
        out.append(sec)
    return out


# Additional detail appended to numbered sections (merged by merged_sections()).
EXTRA = {}

EXTRA["Apex Systems"] = {
    "2": [
        H("Component inventory"),
        T([["Component", "Responsibility", "Scaling and data notes"],
           ["Account service", "Customer, premise, service point and contract records; hierarchy for commercial accounts", "Read replicas per zone; 38 million historical rows partitioned by billing year"],
           ["Rating service", "Applies slab, seasonal, subsidy and sewerage-linked tariffs; effective-dated tariff versions", "Stateless; 12 to 48 pods; rating throughput 2,100 accounts per second per 12 pods"],
           ["Bill presentation service", "Generates bill PDFs in 4 languages with QR code for UPI payment", "Object storage with 7-year retention; PDF render 400 bills per second"],
           ["Payments service", "Online, counter and agent collections; allocation to bills; refunds and reversals", "Idempotent API; daily settlement file reconciliation with banks"],
           ["Case management", "Complaints, service requests, field work orders, SLA timers", "Event driven; escalation rules configured by Board staff"],
           ["Notification service", "SMS, email, WhatsApp and push messages in preferred language", "Template library of 160 messages; quiet hours per customer"],
           ["Analytics store", "Operational dashboards, revenue assurance reports, exception analytics", "Columnar store refreshed every 5 minutes from the event stream"]],
          [0.20, 0.44, 0.36]),
        H("Non-functional targets"),
        T([["Attribute", "Target", "How verified"],
           ["Portal page response (95th percentile)", "Under 1.2 seconds at 2,500 concurrent users", "Performance test in phase 4, repeated after each release"],
           ["Billing run", "1.2 million accounts in under 3 hours; 3 million in under 7 hours", "Synthetic run at 3 million accounts, August 2026"],
           ["Availability", "99.95 percent monthly", "Gateway probes every 30 seconds; monthly SLA report"],
           ["Recovery", "RPO 5 minutes, RTO 30 minutes", "Twice-yearly disaster recovery test with the Board present"],
           ["Accessibility", "WCAG 2.1 level AA for portal", "Independent accessibility audit before UAT"]],
          [0.28, 0.36, 0.36]),
    ],
    "4": [
        H("Data migration plan"),
        "Data migration is run as a controlled sub-project with its own lead and its own exit gates. Legacy data is "
        "extracted read-only into a staging area, profiled, cleansed, transformed into the new account model and loaded. "
        "Every load produces a reconciliation pack that the Board's finance team signs.",
        T([["Step", "Weeks", "Activity", "Control"],
           ["Profile", "3-8", "Profile 38 million billing records, 1.2 million accounts, 2.9 million payment histories; identify duplicates, orphans, invalid tariffs", "Data quality scorecard reviewed weekly"],
           ["Cleanse", "9-20", "Two cleansing cycles with Board data stewards; merge duplicate customers; fix invalid meter links", "Steward sign-off on every merge rule"],
           ["Mock 1", "20-23", "Full load of accounts and 24 months of billing history; measure load time and error rate", "Record count 100 percent; value match target 99.9 percent"],
           ["Mock 2", "25-28", "Full history load, open balances and deposits; parallel bill calculation for 50,000 accounts", "Parallel bill variance under 0.05 percent"],
           ["Mock 3", "30-32", "Dress rehearsal of cutover with timing; rollback tested", "Value match 99.98 percent; open balances exact"],
           ["Cutover", "37", "Final delta load over a weekend freeze; rollback decision point at hour 20", "Go or no-go signed by Board sponsor"]],
          [0.10, 0.09, 0.51, 0.30]),
        H("Test strategy"),
        T([["Test level", "Scope", "Entry / exit", "Volume"],
           ["Unit and component", "Services and rules, run in CI on every commit", "Coverage at least 80 percent on billing services", "About 9,000 automated tests"],
           ["Contract tests", "Every integration interface against SAP and MDM simulators", "All contracts green before certification gate", "320 contract cases"],
           ["System integration", "End-to-end meter-to-cash scenarios", "No open Severity 1 or 2 defects", "620 scenarios"],
           ["Performance", "Billing run, portal load, API spikes, failover", "Targets in Section 2 met on two consecutive runs", "6 scripted load profiles"],
           ["Security", "SAST, DAST, dependency scan, independent VAPT", "No open critical or high findings", "Per release and six-monthly"],
           ["User acceptance", "Board users in 3 pilot zones, 4 weeks", "Signed UAT certificate, 95 percent training completion", "480 business scripts"]],
          [0.18, 0.34, 0.30, 0.18]),
    ],
    "5": [
        H("Responsibility matrix (RACI)"),
        T([["Activity", "Apex delivery", "Apex architect", "Board PMO", "Board business owner"],
           ["Project plan and reporting", "A / R", "C", "R", "I"],
           ["Tariff catalogue sign-off", "C", "C", "I", "A / R"],
           ["Interface control documents", "A", "R", "C", "C"],
           ["SAP and MDM environments", "C", "C", "A / R", "I"],
           ["Data cleansing decisions", "C", "C", "I", "A / R"],
           ["UAT execution", "C", "I", "A", "R"],
           ["Go-live decision", "R", "C", "C", "A"]],
          [0.28, 0.17, 0.17, 0.16, 0.22]),
        "R = responsible, A = accountable, C = consulted, I = informed.",
        H("Sample fortnightly status report (illustrative extract)"),
        T([["Item", "Status", "Comment"],
           ["Schedule", "Green", "Sprint 7 of 13 complete; velocity 46 points against plan of 44"],
           ["Scope", "Green", "2 change requests approved, both within contingency of 120 person-days"],
           ["Risk", "Amber", "SAP test client refresh delayed 4 days; simulator in use; escalated to Board PMO"],
           ["Quality", "Green", "Open defects: 0 Severity 1, 3 Severity 2, 41 Severity 3; automation pass rate 98.6 percent"],
           ["Budget", "Green", "Earned value index 1.02; 41 percent of implementation fee invoiced against 40 percent progress"]],
          [0.16, 0.12, 0.72]),
    ],
    "7": [
        T([["Risk", "Impact", "Control", "Residual"],
           ["Insider misuse of privileged access", "High", "Just-in-time access, approvals, session recording, monthly privileged access review", "Low"],
           ["Misconfiguration of cloud storage", "High", "Policy-as-code scanning, deny-by-default network rules, weekly posture report", "Low"],
           ["Denial of service on portal", "Medium", "Edge protection, rate limiting, autoscaling, tested at 5x peak", "Low"],
           ["Loss of key person in project", "Medium", "Named deputies, documented design, cross-training in first 12 weeks", "Medium"],
           ["Integration defects found late", "Medium", "Contract tests on every build, certification gate in week 26", "Low"],
           ["Training insufficient for zone staff", "Medium", "Sandbox practice, 22 champions, completion gate at 95 percent", "Low"]],
          [0.26, 0.10, 0.52, 0.12]),
        H("Compliance mapping"),
        T([["Obligation", "Platform control", "Evidence provided to Board"],
           ["DPDP Act consent and purpose limitation", "Consent ledger with purpose tags; field-level masking for agents", "Consent report, DPIA, sample masked views"],
           ["Data residency in India", "All stores and backups in Indian regions; no cross-border replication", "Hosting attestation and architecture diagram"],
           ["Audit and retention", "Immutable logs, 7-year retention, tamper-evident hashing", "Quarterly audit log extracts"],
           ["Financial reconciliation", "Daily payment settlement matching, exception queues", "Daily reconciliation report to Board finance"],
           ["Vendor security assurance", "ISO 27001:2022 certificate, SOC 2 Type II report", "Certificate and report summary under NDA"]],
          [0.28, 0.40, 0.32]),
    ],
    "8": [
        H("Service level indicators and reporting"),
        T([["Indicator", "Target", "Measurement"],
           ["Platform availability", "99.95 percent per month", "API gateway probes every 30 seconds"],
           ["Billing run completion", "Within 8-hour overnight window, 100 percent of cycles", "Run log reviewed by service manager"],
           ["Payment posting latency", "95 percent within 2 minutes of gateway confirmation", "Payments service metrics"],
           ["P1 response / resolution", "30 minutes / 4 hours", "Ticket timestamps"],
           ["P2 response / resolution", "2 hours / 8 hours", "Ticket timestamps"],
           ["Backup success", "100 percent of scheduled backups; restore test quarterly", "Backup system report"],
           ["Customer satisfaction on service desk", "At least 4.3 out of 5", "Post-ticket survey"]],
          [0.30, 0.38, 0.32]),
        "A monthly service report with availability, incident trends, problem records, capacity forecast and "
        "security events is delivered by working day 5. Major incidents receive a written post-incident review "
        "within 5 working days. The service desk escalation path runs from the service desk lead to the service manager, "
        "delivery director and, for sustained P1 incidents beyond 8 hours, the Apex managing director.",
    ],
    "9": [
        "Both references have agreed to reference calls and a site visit. The Sundara programme is the closest analogue "
        "to this contract: a water utility with a customer base of 800,000 connections, SAP integration and a portal in "
        "three languages. Lessons carried into this proposal include starting tariff workshops in week 1, freezing tariff "
        "scope at design sign-off and rehearsing cutover three times.",
        T([["Capability area", "Apex evidence", "Count"],
           ["Utility billing implementations", "Water, electricity and distribution clients", "6 in 8 years"],
           ["SAP S/4HANA integrations", "Finance postings with IDoc and OData", "4"],
           ["Platform security audits", "ISO 27001:2022, SOC 2 Type II, VAPT every six months", "Continuous since 2021"],
           ["Cutovers of more than 500,000 accounts", "Weekend freeze with rollback tested", "3"]],
          [0.38, 0.42, 0.20]),
    ],
    "11": [
        H("Appendix D: Training plan summary"),
        T([["Audience", "People", "Duration", "Format"],
           ["Board super-users and champions", "22", "5 days", "Classroom plus sandbox exercises"],
           ["Contact-centre and counter agents", "320", "2 days", "Train-the-trainer in 30 sessions"],
           ["Finance and revenue assurance", "45", "2 days", "Workshops on reconciliation and adjustments"],
           ["Field supervisors", "60", "1 day", "Mobile work-order training"],
           ["IT operations", "18", "5 days", "Run, monitor, deploy and recover the platform"]],
          [0.36, 0.14, 0.14, 0.36]),
        H("Appendix E: Exit and transition"),
        "At contract end or termination Apex provides all Board data in documented open formats within 30 days, "
        "retains no copy after written confirmation, and provides up to 12 weeks of transition support at the "
        "rate card. Source configuration (tariffs, templates, workflows) is exported in machine-readable form.",
    ],
}

EXTRA["NexaWorks"] = {
    "1": [
        H("About NexaWorks"),
        "NexaWorks Technologies was founded in 2016 and has 210 employees, of whom 95 work in the utilities practice. "
        "The company has been profitable for six consecutive years with annual revenue of about INR 190 crore. "
        "Utilities account for 62 percent of revenue and the NexaBill product is maintained by a dedicated team of "
        "34 engineers. Our delivery organisation is certified to ISO 9001 and ISO 27001 and uses a single "
        "delivery handbook that every programme must follow.",
        "Our guiding principle is that a utility programme succeeds when the customer can see its status at any "
        "time. Every Board stakeholder will have access to the same plan, risk register and defect dashboard that "
        "our own managers use.",
    ],
    "2": [
        H("Security and operations architecture"),
        T([["Layer", "Design", "Detail"],
           ["Network", "Segmented VPC with public, application and data subnets", "Web application firewall in front of the portal; private connectivity to Board SAP over IPsec VPN"],
           ["Application", "Containerised services on managed Kubernetes", "Rolling releases, readiness probes, automatic restart; maximum 2 minutes unavailability per release"],
           ["Data", "Primary database cluster, hot standby, nightly full and 15-minute incremental backups", "35-day online retention, 7-year archive of billing documents"],
           ["Observability", "Central logging, metrics and tracing", "Alerts to the 24x7 service desk; dashboards available to Board operations team"],
           ["Identity", "Single sign-on for staff, OTP and password for customers", "MFA mandatory for staff and administrators"]],
          [0.15, 0.38, 0.47]),
        H("Customer channels"),
        B("Web portal and mobile app: bill view and download, payment by UPI and card, meter reading submission, complaint tracking, outage notices.",
          "Agent desktop: one screen showing customer, billing, payments, open cases and field visits, with scripted flows for the 25 most common call reasons.",
          "Notifications: bill ready, due date, payment received, disconnection warning and outage messages in 3 languages (English, Hindi and one regional language chosen by the Board).",
          "Field requests: work orders pushed to a crew mobile app with photo capture and status updates written back to the customer record."),
    ],
    "3": [
        H("Integration test and cutover safeguards"),
        T([["Safeguard", "Description", "When"],
           ["Interface specifications", "Message formats, field mappings, error codes, volumes and timings documented and signed", "End of Gate 2 (week 10)"],
           ["Mock endpoints", "Simulated SAP and MDM responses so development is not blocked by environment delays", "Weeks 5-20"],
           ["Reconciliation reports", "Daily comparison of billing totals to SAP postings, with variances above INR 1,000 flagged", "From G3 onwards"],
           ["Retry and replay", "Failed messages retried 5 times, then parked in an exception queue visible to support staff", "Production"],
           ["Cutover rehearsal", "Two rehearsals including interface switchover and rollback", "Weeks 26 and 28"]],
          [0.22, 0.52, 0.26]),
    ],
    "4": [
        H("Data migration plan"),
        T([["Stage", "Weeks", "Activity", "Exit control"],
           ["Source analysis", "5-8", "Inventory legacy tables, interfaces and reports; profile quality for 14 years of history", "Profiling report accepted by Board data owner"],
           ["Cleansing sprint", "8-12", "Resolve duplicate customers, invalid addresses, missing meter links, orphan payments", "Error rate below 0.5 percent of records"],
           ["Mapping and rules", "9-14", "Field-by-field mapping, transformation rules, tariff history mapping", "Signed mapping workbook"],
           ["Mock migration 1", "17", "Load 5 years of history and all open items; measure timings", "Counts match 100 percent"],
           ["Mock migration 2", "22", "Load full history; parallel bill run on 40,000 accounts", "Bill variance below 0.1 percent"],
           ["Mock migration 3", "26", "Dress rehearsal with cutover timings and rollback test", "Value match 99.95 percent, open balances exact"],
           ["Final migration", "29", "Weekend freeze, delta load, reconciliation, sign-off", "Board finance sign-off"]],
          [0.15, 0.09, 0.50, 0.26]),
        H("Test strategy"),
        T([["Level", "Scope", "Responsibility", "Exit criteria"],
           ["Unit and build verification", "All services, every build", "NexaWorks developers", "No failing build for 5 consecutive days before G3 exit"],
           ["System integration testing (SIT)", "Meter-to-cash flows with SAP and MDM", "NexaWorks testers", "All priority 1 scenarios pass; no open Severity 1"],
           ["Performance testing", "Billing run and 1,500 concurrent portal users", "NexaWorks with Board IT observer", "Billing run under 5 hours at 1.5 million accounts"],
           ["User acceptance testing (UAT)", "Business scripts by Board users in all 11 zones", "Board business owners", "UAT certificate; open Severity 2 defects have agreed workaround"],
           ["Security testing", "VAPT by independent firm", "NexaWorks CISO", "No open high or critical findings at go-live"],
           ["Operational acceptance", "Failover, backup restore, monitoring, runbooks", "NexaWorks operations", "Failover completed within 2 hours"]],
          [0.22, 0.30, 0.22, 0.26]),
        H("Cutover plan"),
        "Cutover is planned for a weekend in week 29 after a billing cycle close. The cutover manager owns a minute-by-minute "
        "runbook of about 180 steps. Decision points are fixed at T-48 hours (readiness review), T-12 hours "
        "(data freeze) and T+20 hours (go or rollback). Legacy remains read-only for 90 days and the rollback "
        "path is tested in rehearsal two. Hypercare begins immediately with a daily 09:00 stand-up and an on-site "
        "team of 6 at HQ and zone offices.",
    ],
    "5": [
        H("Responsibility matrix (RACI)"),
        T([["Activity", "NexaWorks PM", "NexaWorks architect", "Board PMO", "Board business owner"],
           ["Gate planning and reporting", "A / R", "C", "R", "I"],
           ["Solution design sign-off", "R", "A", "C", "C"],
           ["SAP and MDM interface specification", "R", "A", "C", "I"],
           ["Environment provisioning (Board side)", "C", "C", "A / R", "I"],
           ["Data cleansing decisions", "C", "C", "I", "A / R"],
           ["UAT", "C", "I", "R", "A"],
           ["Go-live approval", "R", "C", "C", "A"]],
          [0.30, 0.15, 0.17, 0.16, 0.22]),
        "R = responsible, A = accountable, C = consulted, I = informed.",
        H("Sample weekly project board report (illustrative extract)"),
        T([["Area", "Status", "Detail"],
           ["Gate", "G3 - week 14", "Sprint 3 of 4 complete; 71 of 96 stories accepted"],
           ["Schedule", "Green", "Critical path through SAP interface; float 6 days"],
           ["Risks", "Amber", "R1: SAP test environment arrived 3 days late; mock endpoints in use; mitigation owner Integration lead"],
           ["Defects", "Green", "0 Severity 1, 2 Severity 2, 28 Severity 3 open"],
           ["Decisions needed", "Action", "Board to confirm late-fee policy wording by week 15"]],
          [0.16, 0.16, 0.68]),
        T([["ID", "Additional risk", "Probability / impact", "Mitigation", "Owner"],
           ["R6", "Tariff policy changes during build", "Medium / Medium", "Scope freeze at G2 exit; change board; fast-track path for statutory changes", "Business analyst lead"],
           ["R7", "Payment gateway certification delay", "Low / High", "Two gateways in parallel; certification started in week 8", "Integration lead"],
           ["R8", "Performance below target at scale", "Low / High", "Early performance test in week 18 on a 50 percent scale environment", "Solution architect"],
           ["R9", "Cutover overruns weekend window", "Medium / High", "Two rehearsals; hour-20 rollback decision; delta load tooling", "Cutover manager"],
           ["R10", "Support transition gaps", "Low / Medium", "Service desk shadowing from week 24; runbooks signed at G5", "Operations manager"],
           ["R11", "Zone office connectivity limits agent desktop", "Medium / Medium", "Low-bandwidth mode tested in 3 zones; fallback to HQ queue", "Change lead"]],
          [0.07, 0.24, 0.17, 0.38, 0.14]),
    ],
    "7": [
        T([["Control domain", "Control", "Frequency"],
           ["Access management", "Access requests approved by Board data owner; leavers removed within 24 hours", "Continuous; quarterly recertification"],
           ["Vulnerability management", "Authenticated scans; critical patches within 7 days, high within 30 days", "Weekly scans"],
           ["Backup and recovery", "15-minute incremental, nightly full; restore test", "Quarterly restore test"],
           ["Logging", "Audit trail on billing adjustments, refunds and tariff changes retained 5 years", "Continuous"],
           ["Incident response", "Incident response within 2 hours; Board notified of confirmed personal-data incident", "On event; annual exercise"],
           ["Third-party assurance", "ISO 27001 surveillance audit; VAPT by independent firm", "Annual"]],
          [0.24, 0.52, 0.24]),
    ],
    "8": [
        H("Service management processes"),
        T([["Process", "How it works", "Output to Board"],
           ["Incident management", "24x7 service desk logs, triages and routes; major incident manager appointed for every P1", "Incident report in 5 working days"],
           ["Problem management", "Root cause analysis for P1 and repeated P2; known-error database shared with Board", "Monthly problem log"],
           ["Change management", "Standard, normal and emergency changes with Board approval for normal changes", "Change calendar"],
           ["Release management", "Quarterly minor release, 14 days' notice, regression test report", "Release notes and test report"],
           ["Capacity management", "Monthly trend of connections, transactions and billing run time", "Quarterly capacity forecast"],
           ["Service reviews", "Monthly operations review, quarterly roadmap and security review", "Minutes and action log"]],
          [0.20, 0.52, 0.28]),
        "Support is staffed by 14 engineers on a rotating shift pattern in two locations (Bengaluru and Pune) so that the "
        "service desk is never single-site. The named account manager has 8 years of experience with utility customers "
        "and meets the Board monthly. Availability is measured at the application login transaction, probed every minute.",
    ],
    "9": [
        T([["Capability", "NexaWorks evidence"],
           ["Utility implementations", "9 in 7 years; 8 of 9 live on the planned date"],
           ["Largest deployment", "Lakeview Municipal Water, 650,000 connections, 30 weeks"],
           ["SAP integration", "Coastal Gas Distribution and Lakeview"],
           ["Support", "24x7 desk in operation since 2019; average P1 resolution 2 hours 50 minutes over last 12 months"],
           ["Customer satisfaction", "Annual client survey 4.4 out of 5 across utility clients"]],
          [0.30, 0.70]),
    ],
    "11": [
        H("Appendix C: Training plan summary"),
        T([["Audience", "People", "Format and duration"],
           ["Board project team and champions", "26", "3 days classroom plus sandbox"],
           ["Contact-centre and counter agents", "300", "25 classroom sessions of 2 days, groups of 12"],
           ["Finance and revenue teams", "40", "2 days workshops"],
           ["IT operations", "15", "4 days platform administration"]],
          [0.40, 0.14, 0.46]),
        H("Appendix D: Transition and exit"),
        "At the end of hypercare, NexaWorks hands over to the 24x7 service desk using a signed operational readiness "
        "checklist. On exit the Board receives a full data export and configuration export within 30 days and 8 "
        "weeks of reasonable transition assistance at the quoted rate.",
    ],
}


EXTRA["BrightPath Tech"] = {
    "1": [
        H("Our story"),
        "BrightPath Tech began in 2022 in a rented room in Hyderabad with three friends, two laptops and a shared belief "
        "that technology should be simple, beautiful and fast. Since then we have grown into a team of 28 passionate "
        "digital craftspeople. We have never been afraid of a challenge, and we believe that every challenge is simply an "
        "opportunity in disguise. Our founders left larger consulting firms because they felt that big projects had become "
        "slow, heavy and expensive. We set out to prove that there is a better way.",
        "Today we help clients across retail, education and services to put their ideas online. We love what we do, and "
        "our clients tell us that they love working with us because we listen, we move quickly and we are always "
        "available on a messaging app when they need us.",
        H("Our vision, mission and values"),
        T([["Statement", "What it means to us"],
           ["Vision", "To be the most loved digital partner for every organisation that wants to serve its customers better"],
           ["Mission", "To make powerful technology simple, affordable and delightful for everyone"],
           ["Value: Speed", "We believe a good solution delivered quickly is better than a perfect solution delivered late"],
           ["Value: Simplicity", "We remove complexity wherever we can and focus on what matters"],
           ["Value: Care", "We treat every client project as if it were our own business"],
           ["Value: Curiosity", "We keep learning and trying new tools so our clients benefit from the latest ideas"]],
          [0.22, 0.78]),
        H("Why the Board should choose BrightPath"),
        "Choosing a partner is about more than a price list. It is about energy, attitude and trust. Large, "
        "established vendors may bring long lists of credentials, but they also bring long timelines, long meetings and "
        "long invoices. BrightPath offers the Board something different: a nimble team that can start immediately, "
        "work side by side with your people and put a modern customer experience in front of your customers "
        "within one quarter. We believe the Board's customers deserve a digital experience as good as the best "
        "consumer apps they use every day, and we are excited to make that happen.",
        "We also believe in transparency. We will always tell you what is going well and what is not, and we will never "
        "hide behind jargon. If something is difficult, we will say so and work with you to find a way forward.",
    ],
    "2": [
        H("Technology approach"),
        "QuickBill is built on modern, widely used web technologies and is designed to be flexible. The look and feel "
        "can be adapted to the Board's branding, and screens can be rearranged by our developers in a matter of hours. "
        "Because the platform is low-code, many changes that would take weeks on a traditional system can be made in "
        "days. We believe that this agility is a key advantage for an organisation that wants to improve continually.",
        T([["Feature", "Benefit to the Board"],
           ["Drag-and-drop screen builder", "Faster changes and lower cost"],
           ["Reusable billing templates", "Quicker setup of tariffs and bill formats"],
           ["Responsive design", "Works well on phones, tablets and computers"],
           ["Cloud hosting", "No servers to buy or maintain"],
           ["Dashboard widgets", "Simple visual summaries of bills and payments"],
           ["Modern payment options", "Customers can pay in a way that suits them"]],
          [0.32, 0.68]),
        H("Future roadmap (aspirational)"),
        "Beyond the first release we hope to explore a number of exciting opportunities together with the Board. "
        "These ideas are part of our vision for the platform and will be prioritised based on the Board's feedback and "
        "our available capacity.",
        B("Artificial intelligence assistant to answer common customer questions.",
          "Predictive analytics to help the Board understand consumption trends.",
          "Chat-based bill payments through popular messaging applications.",
          "Smart alerts for unusual water usage that may indicate leaks.",
          "A community feature where customers can share water-saving tips.",
          "Exploration of blockchain for tamper-proof records, if the Board is interested."),
        "Timelines for these items have not been fixed, and they are not included in the price or in the 16-week plan.",
        H("Scalability and performance"),
        "We are confident that QuickBill will perform well for the Board. The platform has been designed with growth "
        "in mind, and we will monitor performance and increase resources when needed. Our approach to performance is "
        "to start small, measure and improve. We do not currently have performance test results for volumes similar to "
        "the Board's customer base, but we will carry out testing before go-live if time permits.",
    ],
    "3": [
        H("Our philosophy on integration"),
        "Modern organisations rely on many systems, and we believe that systems should work together smoothly. Our "
        "philosophy is to keep integrations simple and to avoid unnecessary complexity. File-based exchange has been "
        "used successfully by businesses for many years and it is easy to understand, easy to support and easy to "
        "change. Where the Board wishes to move to real-time connections, we will be happy to discuss options once the "
        "first release is live and the team has had the opportunity to learn from real usage.",
        "We have a flexible mindset and enjoy working with other vendors' teams. We expect that the Board's finance "
        "and meter systems vendors will cooperate to share the information we need. The details of file formats, "
        "schedules and mappings will be agreed with them in due course.",
    ],
    "4": [
        H("Our way of working"),
        "At BrightPath we practise agile ways of working. Agile means that we deliver in small steps, learn from "
        "feedback and adapt quickly. We believe this is the best way to build software in a world that changes fast. "
        "Our teams are self-organising, empowered to make decisions and focused on delivering value.",
        T([["Principle", "How we practise it"],
           ["Customer collaboration", "A weekly demonstration and a shared messaging channel with the Board"],
           ["Working software", "We show running screens, not long documents"],
           ["Responding to change", "Requirements can change at any time and we adapt"],
           ["Continuous improvement", "A short retrospective after every cycle"],
           ["Transparency", "A shared board showing what is to do, in progress and done"]],
          [0.28, 0.72]),
        H("Best practices we follow"),
        B("We follow industry best practices for software development wherever practical.",
          "We try to write clean, readable and maintainable configuration.",
          "We use version control for our work.",
          "We believe in testing early and testing often.",
          "We aim to communicate clearly, openly and respectfully.",
          "We strive to deliver a great experience for every user."),
        H("Project governance"),
        "The project lead will be the Board's main contact and will provide regular updates. A steering meeting can be held "
        "whenever the Board wishes. Reports are provided on request. Risks and issues will be discussed in the weekly "
        "call and addressed quickly.",
        H("Training and handover"),
        "We provide two training sessions in the price. Sessions are delivered online or in person, subject to travel "
        "arrangements, and include a short presentation, a demonstration and time for questions. A handover note "
        "summarising how the system is set up will be provided at the end of the project. Additional training "
        "can be arranged at an additional fee.",
        H("Data migration"),
        "The Board's IT team will extract existing customer data and provide it to us in a spreadsheet or file format. "
        "We will provide guidance on how the data should be organised. The Board will need to check the data after it has "
        "been loaded. We have not yet seen the structure or volume of the Board's data, so the effort needed for migration "
        "cannot be estimated precisely at this stage.",
    ],
    "5": [
        H("How we plan"),
        "Our plan is deliberately lightweight, because we believe that heavy plans slow teams down. The stages in the table "
        "above give a general view of how the project will flow. Exact tasks will be organised week by week in "
        "consultation with the Board. If something takes longer than expected we will work extra hours to stay on track, "
        "and we will keep the Board informed.",
        T([["Week", "What the Board can expect"],
           ["Week 2", "A first look at the new screens"],
           ["Week 6", "Demonstration of billing and the customer portal"],
           ["Week 10", "Demonstration of payments"],
           ["Week 14", "Testing support from the Board's users"],
           ["Week 16", "Go-live"]],
          [0.2, 0.8]),
        "We accept that the plan is ambitious. The Board's quick decisions and availability will help us deliver on "
        "time.",
    ],
    "6": [
        H("Why our price is lower"),
        "We are often asked how we can offer such competitive prices. The answer is that we are a lean company with low "
        "overheads, we do not maintain expensive offices or large sales teams, and we focus on our own platform so that "
        "we do not pay licence fees to other vendors. We pass these savings on to our clients.",
        T([["Price element", "Comment"],
           ["Implementation and customisation", "Based on our estimate of the effort needed; may change when requirements are confirmed"],
           ["QuickBill licence", "Three-year licence; renewal terms to be discussed"],
           ["Training", "Two sessions; further sessions on request"],
           ["Hosting", "Not included; cost depends on the size of the server chosen"],
           ["Changes after contract", "Quoted separately at our standard rates"]],
          [0.35, 0.65]),
        "Our pricing is designed to be easy to understand. We do not charge for ideas, and we will always try to be fair "
        "with any additional requests.",
    ],
    "7": [
        H("Our commitment to security"),
        "Security is important to everyone at BrightPath. We believe that protecting customer information is the right "
        "thing to do, and we aim to follow good practices wherever we can. Our team is aware of common online threats, "
        "and we try to keep our software up to date. As a growing company we intend to strengthen our security "
        "programme over time, including the formal certification mentioned above.",
        "We will discuss specific security requirements with the Board after contract award and will do our best to meet "
        "them within the time and budget available.",
    ],
    "8": [
        H("Our service philosophy"),
        "We believe great support is about people, not processes. Our team is friendly, approachable and eager to help. "
        "After go-live we will remain in close touch with the Board's team through email and messaging, and we will "
        "do our best to resolve questions as quickly as we can. If a serious problem occurs outside working hours we "
        "will try to respond when possible.",
        T([["Support item", "Provision"],
           ["Hours", "Monday to Friday, 9 am to 6 pm"],
           ["Channel", "Email, with phone to the project lead in working hours"],
           ["Response", "We aim to respond within one business day"],
           ["Formal SLA", "Not currently offered; can be discussed"],
           ["Warranty", "Defects found shortly after go-live will be fixed"]],
          [0.28, 0.72]),
    ],
    "9": [
        H("About our past work"),
        "We are proud of the portals we have built. BookNest Retail launched a new online shop with our help and "
        "was delighted by the result. Learnwell Academy now has a student portal that students enjoy using. Fresh "
        "Basket Stores wanted an easy way for customers to order groceries online, and we delivered it in a few weeks. "
        "These projects taught us a great deal about building customer-friendly web experiences, and we are eager to "
        "apply that learning to the water sector.",
        "We recognise that the Board is a public utility with different needs from our previous clients. This would be "
        "our first utility billing project. We are keen to learn about the water sector and we are confident that our "
        "enthusiasm and quick learning will bring success.",
        "We understand that the Board may like to speak to our clients. We would be happy to discuss references with "
        "the Board at a suitable time.",
    ],
    "11": [
        H("Appendix C: Meet the team"),
        T([["Name (fictional)", "Role", "Background"],
           ["Arjun Rao", "Founder and project lead", "Studied computer applications; started BrightPath in 2022; enjoys cricket and hiking; loves solving problems with simple tools"],
           ["Sana Qureshi", "Senior developer", "5 years of web development; built portals for retail clients; enthusiastic about user experience design"],
           ["Kiran Babu", "Developer", "3 years of experience; works on payment pages and forms; keen learner of new frameworks"],
           ["Pooja Nair", "Developer", "3 years of experience; focuses on mobile layouts and styling; passionate about accessibility"],
           ["Dev Malhotra", "Developer", "2 years of experience; supports portal features and testing; interested in data visualisation"]],
          [0.20, 0.22, 0.58]),
        H("Appendix D: Frequently asked questions"),
        T([["Question", "Answer"],
           ["Can you really finish in 16 weeks?", "Yes. We are a small, focused team and we believe in moving fast."],
           ["Is QuickBill used by other water boards?", "QuickBill is a new platform and is evolving every month with feedback from our clients."],
           ["What happens if requirements change?", "We welcome change. Changes may affect price and timing and will be discussed."],
           ["Will our data be safe?", "We take data protection seriously and will follow applicable laws."],
           ["Do you offer 24x7 support?", "Our standard support hours are Monday to Friday. Other arrangements can be discussed."],
           ["Can you integrate with our other systems?", "Probably. We will look at this after the contract is signed."],
           ["Who owns the software?", "BrightPath owns QuickBill; the Board receives a licence for the term."]],
          [0.34, 0.66]),
        H("Appendix E: Glossary"),
        T([["Term", "Meaning"],
           ["Agile", "A flexible way of running projects in short cycles"],
           ["API", "A way for two systems to talk to each other"],
           ["Cloud", "Computers accessed over the internet"],
           ["Customisation", "Changing a product to suit a client"],
           ["UX", "User experience; how pleasant a product is to use"],
           ["Go-live", "The day the system starts being used for real"]],
          [0.25, 0.75]),
        H("Appendix F: General terms and conditions (summary)"),
        B("Services are provided on the basis of the proposal and the requirements known at the date of this proposal.",
          "Timelines depend on timely feedback, approvals and content from the Board; delays may extend the schedule.",
          "BrightPath retains ownership of QuickBill, its templates, tools and methods. The Board receives a non-exclusive licence for the term.",
          "Liability of BrightPath is limited to the fees paid in the preceding twelve months, to the extent permitted by law.",
          "Neither party is liable for events beyond its reasonable control, including cloud provider outages.",
          "Either party may terminate with 30 days' written notice; fees for work completed are payable.",
          "Invoices are payable within 15 days. Late payments may incur interest.",
          "Confidential information will be protected with reasonable care.",
          "These terms may be updated by agreement in writing."),
    ],
}


EXTRA["Orbit Digital"] = {
    "1": [
        H("Company history"),
        "Orbit Digital was established in 2008 in Bengaluru by a group of former enterprise software professionals who "
        "saw an opportunity to bring modern technology to the utilities sector. In our first five years we focused on "
        "billing and customer information systems for electricity distribution companies. From 2013 we broadened our "
        "offering to water and gas utilities, and in 2017 we launched the first version of UtilityOne. In 2021 we "
        "opened our second delivery centre, and in 2024 we crossed the milestone of 120 employees in our utilities "
        "practice. Throughout this journey we have remained committed to a simple idea: that utilities deserve "
        "technology partners who truly understand their world.",
        T([["Year", "Milestone"],
           ["2008", "Orbit Digital founded in Bengaluru"],
           ["2011", "First electricity billing engagement completed"],
           ["2013", "Entry into the water and gas sectors"],
           ["2017", "UtilityOne first released"],
           ["2019", "Bengaluru service centre extended to 24x7 coverage for critical incidents"],
           ["2021", "Second delivery centre opened"],
           ["2024", "Utilities practice reaches 120 staff"],
           ["2025", "Northbank Water Utility go-live on UtilityOne"]],
          [0.15, 0.85]),
        H("Our values"),
        "We hold five values close. Partnership means working shoulder to shoulder with clients. Integrity means doing "
        "what we say. Excellence means striving for quality in everything we do. Innovation means looking for better "
        "ways. Sustainability means caring about the long-term impact of our work on communities and the environment. "
        "These values guide our daily decisions and are reflected in the way we build and support our solutions.",
        H("Why Orbit Digital"),
        "Choosing a billing partner is a decision that will shape a utility for a decade. We believe the most "
        "reliable predictor of success is experience, and few firms can match ours. Our consultants have seen the "
        "pitfalls and know how to avoid them. Our clients tell us that our people are our greatest strength: "
        "knowledgeable, calm under pressure and genuinely invested in their success.",
    ],
    "2": [
        H("Product overview"),
        "UtilityOne is more than a billing system. It is an integrated suite that supports the entire customer "
        "relationship, from connection request to final bill. The suite has been continuously enhanced based on "
        "feedback from our user community. Its modular design allows utilities to adopt functionality at their own pace, "
        "while a common customer record ensures a consistent experience across channels.",
        T([["Module", "Highlights"],
           ["Billing and rating", "Flexible tariffs, multiple bill cycles, estimated billing, adjustments and rebates"],
           ["Collections", "Payment plans, reminders, disconnection workflow"],
           ["Customer portal", "Account view, online payment, service requests, notifications"],
           ["Contact centre", "Case management, scripts, knowledge base"],
           ["Field service", "Work order management and scheduling"],
           ["Reporting and dashboards", "Standard reports and a configurable dashboard"]],
          [0.28, 0.72]),
        H("Roadmap and innovation"),
        "Orbit continues to invest in UtilityOne. Our product roadmap includes enhanced analytics, a refreshed user "
        "interface, expanded mobile capabilities and further use of automation. Roadmap items are subject to change "
        "and will be shared with customers through our user forum. We also take part in industry events and working "
        "groups to keep pace with the changing needs of utilities.",
        H("Hosting and operations"),
        "UtilityOne will be hosted in a cloud region in India. Orbit will manage the environment, apply updates and "
        "monitor performance. Exact environment sizes, redundancy arrangements and recovery objectives will be "
        "proposed in design and agreed with the Board.",
    ],
    "3": [
        H("Integration principles"),
        "We have extensive experience of connecting UtilityOne with the systems that utilities depend on. Our general "
        "principles are to reuse standard connectors where possible, to prefer loosely coupled integration and to test "
        "interfaces thoroughly. We believe that early engagement with the owners of each system is the key to success, "
        "which is why we place such emphasis on discovery. By talking to the right people at the right time we will "
        "reduce risk and make good choices.",
        T([["Topic", "Position"],
           ["Interface technology", "To be confirmed in discovery"],
           ["Data volumes and frequencies", "To be confirmed in discovery"],
           ["Error handling and reconciliation", "To be confirmed in discovery"],
           ["Environments and test data", "To be confirmed in discovery"],
           ["Effort and price for integration", "Allowance only; to be confirmed after discovery"],
           ["Responsibility split with Board IT and SAP team", "To be confirmed in discovery"]],
          [0.40, 0.60]),
        "We will provide an integration approach document at the end of discovery. Until then we cannot commit to "
        "specific interface designs, performance figures or dates for integration milestones.",
    ],
    "4": [
        H("Methodology overview"),
        "Orbit's delivery methodology, OrbitWay, brings together good practices from many years of experience. It "
        "provides a common language for our teams and clients, a consistent set of deliverables and a flexible "
        "framework that can be adapted to each engagement. OrbitWay is not a rigid process; it is a toolkit that our "
        "consultants apply with judgement.",
        T([["Phase", "Purpose", "Typical activities"],
           ["Discovery", "Understand the organisation and agree the way forward", "Workshops, interviews, review of existing systems, definition of scope"],
           ["Configuration and integration", "Build the solution", "Configure UtilityOne, develop interfaces, prepare data"],
           ["Testing", "Check that it works", "Test planning, test execution, defect resolution, user acceptance"],
           ["Deployment", "Bring the solution into use", "Training, cutover, go-live support"]],
          [0.22, 0.34, 0.44]),
        H("Governance and communication"),
        "Each engagement has a governance structure appropriate to its size. Typically this includes a steering "
        "committee that meets periodically, a project board and regular status reports. The engagement partner "
        "remains accessible to the Board throughout. Communication is encouraged at all levels, and we find that "
        "open, honest dialogue is the foundation of successful projects.",
        H("Quality and risk management"),
        "Quality is everyone's responsibility at Orbit. Our consultants follow internal quality guidelines and "
        "deliverables are reviewed by experienced colleagues. Risks are identified, assessed and monitored throughout "
        "the project. We believe that proactive risk management is the mark of a mature organisation.",
        H("Change management and training"),
        "Successful adoption depends on people. Orbit's approach to change management emphasises stakeholder "
        "engagement, clear communication and practical training. A training approach will be developed during "
        "discovery taking into account the number of users, their roles and the Board's preferences.",
        H("Data migration"),
        "Data migration is a critical activity. Our consultants have migrated data from many legacy systems. The "
        "approach, tools, number of trial loads and reconciliation method will be defined during discovery once the "
        "Board's data has been reviewed.",
    ],
    "5": [
        "The phase durations above are approximate and will be refined at the end of discovery. Factors that may affect "
        "duration include the scope of integrations, data quality, availability of Board staff and the number of "
        "business processes to be configured. Orbit will provide a baseline plan at the end of discovery.",
        T([["Item", "Position"],
           ["Detailed project plan", "After discovery"],
           ["Named milestones and acceptance criteria", "After discovery"],
           ["Team size by phase", "After discovery"],
           ["Go-live date", "Approximately week 36; to be confirmed after discovery"]],
          [0.45, 0.55]),
    ],
    "6": [
        H("Commercial approach"),
        "Orbit prefers a time-and-materials approach for implementation because it provides flexibility and allows "
        "the Board to respond to what is learned during discovery. Many of our clients have found that this approach "
        "leads to better outcomes than fixed prices, which can discourage change. We will share timesheets and monthly "
        "burn-down information so that the Board can monitor effort.",
        T([["Element", "Basis"],
           ["Implementation services", "Time and materials at a blended INR 16,000 per person-day; estimate only"],
           ["Licence and hosting", "Three-year fee; annual increase in line with inflation"],
           ["Training", "Estimated; depends on number of sessions agreed in discovery"],
           ["Integration allowance", "Included in the estimate; may change after discovery"],
           ["Expenses", "Travel and accommodation charged at actuals"],
           ["Taxes", "GST extra"]],
          [0.30, 0.70]),
        "Invoices are issued monthly in arrears for time worked and annually in advance for licences. Payment is due within "
        "30 days.",
    ],
    "7": [
        H("Information security approach"),
        "Orbit takes information security seriously and has an information security management system aligned to "
        "ISO 27001. Our staff receive security awareness training, and our service centre follows documented "
        "procedures. We work with clients to understand their security requirements and to implement appropriate "
        "measures. Specific controls for the Board's environment will be agreed in design.",
    ],
    "8": [
        H("Service approach"),
        "Orbit's service centre in Bengaluru supports clients across several sectors. Support staff are trained on "
        "UtilityOne and have access to engineers when needed. We believe in building long-term relationships and "
        "regularly meet our clients to review service. The support agreement, including service hours, resolution "
        "targets, service credits and reporting, will be finalised with the Board after contract award.",
        T([["Item", "Position"],
           ["Critical incidents", "24x7 coverage; response within 1 hour"],
           ["Other incidents", "Business hours; response times in support agreement"],
           ["Account management", "Named account manager"],
           ["Reviews", "Periodic service reviews"],
           ["Availability target", "To be agreed"]],
          [0.35, 0.65]),
    ],
    "9": [
        H("Client testimonials (summary)"),
        "Our clients regularly tell us that Orbit is a dependable partner. Northbank Water Utility described the programme as "
        "a landmark for the organisation. Riverside Electricity Board commended the professionalism of the project "
        "team. Greenfield Gas Company noted the smooth transition to the new system. Central Plains Water Trust and "
        "Metro Water and Sewerage Board have both continued to work with Orbit for further enhancements.",
        T([["Experience dimension", "Orbit position"],
           ["Utility billing implementations", "22 completed"],
           ["Utility clients", "14"],
           ["References offered", "5, all agreed to be contacted"],
           ["Sectors", "Water, electricity and gas"],
           ["Largest deployment", "1.1 million connections"]],
          [0.45, 0.55]),
    ],
    "10": [
        H("Additional terms (summary)"),
        B("Orbit will provide services in accordance with a master services agreement to be negotiated with the Board.",
          "Intellectual property in UtilityOne remains with Orbit; the Board receives a licence for the term.",
          "Liability is limited to the fees paid under the relevant statement of work.",
          "Either party may terminate for material breach after a 30-day cure period.",
          "Orbit may use subcontractors with the Board's consent.",
          "Confidential information will be protected.",
          "The proposal is valid for 90 days from submission."),
    ],
    "11": [
        H("Appendix C: Consultant profiles"),
        T([["Name (fictional)", "Role", "Profile"],
           ["Suresh Menon", "Engagement partner", "24 years in utilities consulting; led Northbank programme; regular speaker at industry conferences"],
           ["Divya Narayan", "Project manager", "14 years of billing project management; PMP; mentors junior managers"],
           ["Rahul Khanna", "Senior consultant", "11 years in billing configuration; trained over 400 end users across clients"],
           ["Ishita Bose", "Senior consultant", "9 years in customer portals and contact-centre modules"],
           ["Manoj Pillai", "Technical consultant", "10 years in integration and data conversion for utilities"]],
          [0.22, 0.20, 0.58]),
        H("Appendix D: Frequently asked questions"),
        T([["Question", "Answer"],
           ["Will you integrate with SAP S/4HANA?", "Yes, subject to confirmation of the approach in discovery."],
           ["Is the price fixed?", "The implementation price is an estimate on a time-and-materials basis."],
           ["How many consultants will you assign?", "The team size will be confirmed after discovery."],
           ["Can we speak to references?", "Yes. All five references have agreed to be contacted."],
           ["Where is data hosted?", "In a cloud region in India."],
           ["What happens at the end of the contract?", "Data return and transition arrangements will be agreed in the contract."]],
          [0.38, 0.62]),
        H("Appendix E: Corporate social responsibility"),
        "Orbit Digital is committed to being a responsible corporate citizen. We support education programmes for "
        "underprivileged students, encourage employee volunteering and work to reduce the environmental impact of our "
        "operations. Our offices use renewable energy where available and we encourage remote working to reduce travel. "
        "We believe that business should contribute to the communities it serves.",
        H("Appendix F: Glossary"),
        T([["Term", "Meaning"],
           ["Discovery", "Initial phase in which detailed requirements and scope are established"],
           ["OrbitWay", "Orbit's delivery methodology"],
           ["T&M", "Time and materials"],
           ["Blended rate", "Average daily rate across roles"],
           ["MDM", "Meter data management system"],
           ["Statement of work", "Document describing the services for a particular engagement"]],
          [0.25, 0.75]),
    ],
}

EXTRA["BrightPath Tech"]["5"] += [
    H("Roles and responsibilities"),
    T([["Who", "What they do"],
       ["Project lead (BrightPath)", "Talks to the Board, plans the weeks, keeps the team on track"],
       ["Developers (BrightPath)", "Configure QuickBill, build screens, fix problems, run tests"],
       ["Board project contact", "Provides information, attends weekly demo, approves changes"],
       ["Board IT team", "Provides data, finance file formats and test accounts"],
       ["Board business users", "Try the system and share feedback"]],
      [0.32, 0.68]),
    "We have found that clear, friendly communication is the best way to avoid misunderstandings. Where tasks "
    "depend on the Board, we will remind the project contact in the weekly call.",
]
EXTRA["BrightPath Tech"]["10"] = [
    H("Notes on the proposal"),
    "This proposal reflects our understanding of the Board's needs based on the information in the RFP. Where the "
    "RFP is silent we have made reasonable assumptions in the interest of keeping the price low. We would be happy to "
    "review any assumption with the Board during clarification meetings. Items not mentioned in this proposal are "
    "not included. Optional extras, such as additional languages, extra reports and further integrations, can be "
    "added for an additional price once their size is understood.",
    "We want to be a good partner to the Board. If, at any point, the Board feels that the project is not "
    "going as planned, we would welcome an open conversation.",
]
EXTRA["BrightPath Tech"]["11"] += [
    H("Appendix G: Our commitment to sustainability"),
    "As a young company we care about the future. We encourage a paperless office, we choose cloud services that "
    "describe themselves as environmentally conscious, and we support our team to work flexibly. We hope to formalise "
    "our sustainability goals as we grow and to share progress with our clients.",
]

EXTRA["Apex Systems"]["11"] += [
    H("Appendix F: Clarifications offered to the Board"),
    T([["Topic", "Apex position"],
       ["Hosting alternatives", "Single-zone production hosting is available at INR 28,00,000 lower per year, with RTO of 4 hours; not recommended"],
       ["Optional scope", "Additional regional language, INR 9,50,000 per language; extra mobile app features priced per sprint"],
       ["Contract term", "Subscription may be extended for 2 further years at no more than 5 percent annual uplift"],
       ["Source code escrow", "Available with an independent escrow agent at the Board's request"],
       ["Reference visits", "Apex will arrange site visits to Sundara City Water Corporation within 3 weeks of request"]],
      [0.26, 0.74]),
    "Apex is available to meet the evaluation committee for a demonstration of the billing engine, the tariff "
    "simulator and the operations console at the Board's convenience.",
]
EXTRA["NexaWorks"]["6"] = [
    H("Commercial clarifications"),
    T([["Topic", "NexaWorks position"],
       ["Price basis", "Fixed price for the scope in this document; fit-gap items identified in G2 are priced inside the fee"],
       ["Out-of-scope work", "INR 15,000 per person-day after change board approval; estimate provided within 3 working days"],
       ["Hosting growth", "Included to 1.5 million connections; INR 11 per connection per month thereafter"],
       ["Price validity", "120 days from submission"],
       ["Invoice terms", "Net 30 days; implementation invoiced at gate completion; subscription quarterly in advance"],
       ["Service credits", "Applied automatically to the next invoice"],
       ["Contract extension", "Years 4 and 5 at INR 1,70,00,000 per year, with annual uplift capped at 4 percent"]],
      [0.24, 0.76]),
    "The fee does not depend on discovery outcomes: the five gates, the effort behind them and the product "
    "configuration are all included in the implementation price.",
]
EXTRA["NexaWorks"]["10"] = EXTRA["NexaWorks"].get("10", []) + [
    H("Dependencies on the Board"),
    T([["Dependency", "Needed by", "Consequence of delay"],
       ["Executive sponsor and product owner named", "Week 1", "G1 exit delayed day for day"],
       ["Legacy data extracts in agreed format", "Week 8", "Cleansing sprint compressed; contingency of 2 weeks"],
       ["SAP and MDM test environments", "Week 9", "Mock endpoints used; integration testing risk raised"],
       ["Tariff policy decisions", "Week 10", "Change control after scope freeze"],
       ["UAT participants released from duties", "Week 24", "UAT duration extends; go-live date moves"]],
      [0.42, 0.18, 0.40]),
]


EXTRA["BrightPath Tech"]["11"] += [
    H("Appendix H: What clients say about working with us"),
    "We are fortunate to receive kind words from the clients we have worked with. One retail client described the "
    "team as responsive and fun to work with. An education client said the portal exceeded expectations. A services "
    "client appreciated that we always picked up the phone. We treasure this feedback and use it to keep improving.",
    H("Appendix I: Our approach to quality"),
    "Quality matters to us. We try to review each other's work, we test screens on different devices and we invite "
    "clients to try the product early. We believe that quality is a habit rather than a department, and we hope to "
    "build more formal quality practices as our team grows. Over time we would like to introduce checklists, "
    "automated tests and regular quality reviews.",
    T([["Quality activity", "Current practice"],
       ["Peer review", "Developers look at each other's work when time allows"],
       ["Testing", "Developers test their own screens and fix problems found"],
       ["User feedback", "Collected in the weekly demonstration"],
       ["Defect tracking", "Simple shared list"],
       ["Improvement", "Short team discussion after each cycle"]],
      [0.30, 0.70]),
    H("Appendix J: A note on the water sector"),
    "Water is precious, and we are inspired by the Board's mission to deliver a safe and reliable supply to the "
    "region. We have started reading about utility billing, tariff structures and customer service in the water "
    "sector, and we look forward to learning directly from the Board's experts. We believe that fresh eyes can bring "
    "new ideas and that an open, curious attitude is the best way to learn. We are excited by the opportunity to "
    "support the Board's customers with a more convenient digital experience.",
    H("Appendix K: Communication plan"),
    T([["Channel", "Purpose", "Frequency"],
       ["Weekly demonstration call", "Show progress and gather feedback", "Weekly"],
       ["Messaging group", "Quick questions and updates", "Daily as needed"],
       ["Email summary", "Record decisions", "After each call"],
       ["Shared tracker", "Show tasks and status", "Always available"],
       ["Steering meeting", "Review progress with senior stakeholders", "On request"]],
      [0.30, 0.46, 0.24]),
]
EXTRA["BrightPath Tech"]["8"] += [
    H("Continuous improvement after go-live"),
    "After go-live we hope to hold regular conversations with the Board about how the platform is performing and what "
    "could be improved. Suggestions will be collected and considered for future updates. New features may be added "
    "from time to time, and the Board is welcome to benefit from improvements that we make for other clients. "
    "Updates will be applied when convenient and we will let the Board know in advance where possible.",
]

EXTRA["Orbit Digital"]["1"] += [
    H("Our people"),
    "Orbit's strength lies in its people. Our utilities practice brings together business analysts, solution "
    "architects, technical consultants, testers and trainers, many of whom have been with Orbit for more than a decade. "
    "We invest in learning, with every consultant receiving at least 40 hours of training per year, and we encourage "
    "our staff to gain professional certifications. We believe that a stable, experienced team provides continuity "
    "and reassurance to clients, and it is our practice to keep key personnel on an engagement from start to finish "
    "wherever possible.",
    H("Our commitment to the Board"),
    "We are honoured to be invited to respond to this RFP. We understand the importance of the Board's mission and "
    "the trust that customers place in it. If selected, Orbit will bring the full weight of its experience, energy "
    "and commitment to the programme.",
]
EXTRA["Orbit Digital"]["2"] += [
    H("Customer experience vision"),
    "Today's customers expect convenience. UtilityOne's portal is designed to give customers a single place to see "
    "their bills, make payments, request services and receive notifications. We aim to make every interaction "
    "simple, whether the customer is online, on a phone or at a counter. The user interface will be configured with "
    "the Board's branding, and language options will be agreed during design.",
    H("Reporting"),
    "UtilityOne includes standard reports for billing, collections and customer service. The Board will also be able "
    "to define custom reports. A full list of reports and the data warehouse approach will be agreed during design.",
]
EXTRA["Orbit Digital"]["4"] += [
    H("Sample deliverables"),
    T([["Phase", "Typical deliverables"],
       ["Discovery", "Discovery report, scope statement, high-level design, project plan"],
       ["Configuration and integration", "Configured system, interface descriptions, migration scripts"],
       ["Testing", "Test plan, test results, defect log, acceptance certificate"],
       ["Deployment", "Training materials, cutover plan, go-live report, handover"]],
      [0.30, 0.70]),
    "The content, number and timing of these deliverables will be tailored to the Board during discovery.",
]
EXTRA["Orbit Digital"]["7"] += [
    T([["Area", "Orbit position"],
       ["Certification", "ISO 27001 certified"],
       ["Access control", "Role-based access"],
       ["Encryption", "In transit and at rest"],
       ["Audit logging", "Supported by UtilityOne"],
       ["Penetration testing", "Annual"],
       ["Data protection", "Compliance with Indian data protection regulations"],
       ["Incident response", "Per support agreement"],
       ["Disaster recovery objectives", "To be agreed in design"]],
      [0.35, 0.65]),
    "More detailed security documentation can be provided after contract award.",
]
EXTRA["Orbit Digital"]["11"] += [
    H("Appendix G: Our approach to client relationships"),
    "Orbit believes in long-term partnerships. We hold regular executive meetings with key clients, invite clients to "
    "our annual user conference and set up user groups where customers can share experiences. Many of our clients have "
    "worked with us for more than ten years. We see every project as the beginning of a relationship rather than "
    "the end of a transaction. Our account managers are encouraged to understand each client's strategy so that "
    "we can recommend improvements that matter.",
    H("Appendix H: Awards and recognition"),
    "Orbit has been recognised by industry bodies for service quality and customer satisfaction. Our team has "
    "presented at regional utility conferences, and our clients have featured in trade publications. We are proud of "
    "this recognition, which reflects the dedication of our staff.",
]

EXTRA["NexaWorks"]["2"] += [
    H("Reporting and analytics"),
    T([["Report area", "Examples", "Audience"],
       ["Revenue assurance", "Unbilled consumption, estimated read ratio, adjustment trends, write-offs", "Board finance"],
       ["Collections", "Ageing, promise-to-pay, payment channel mix, disconnection candidates", "Revenue manager"],
       ["Service performance", "Complaint volumes, resolution times, repeat contacts", "Customer service head"],
       ["Operations", "Billing run duration, exception queue size, interface backlog", "IT operations"],
       ["Executive", "Monthly one-page scorecard with 12 indicators", "General manager"]],
      [0.22, 0.52, 0.26]),
    "More than 70 standard reports are included. Board staff can build new reports from a governed semantic model "
    "without database access.",
]
EXTRA["NexaWorks"]["9"] += [
    H("Lessons from previous programmes"),
    B("Lakeview: early booking of the SAP test environment avoided the delay we experienced on Coastal Gas; this is now a G1 action.",
      "Coastal Gas: the one-week late go-live came from a client environment delay, which is why we publish a dependency table and escalate in week 9.",
      "Hillstate: the agent desktop adoption curve improved after floor-walkers were added in hypercare, which is standard in this proposal.",
      "Across programmes: three mock migrations consistently reduced cutover defects compared with two."),
]
EXTRA["NexaWorks"]["4"] += [
    H("Quality gates and metrics tracked"),
    T([["Metric", "Target", "Reported"],
       ["Schedule performance index", "At least 0.95", "Weekly"],
       ["Open Severity 1 and 2 defects", "Zero Severity 1 at gate exit", "Weekly"],
       ["Requirement coverage by test", "100 percent of priority 1 requirements", "Per gate"],
       ["Data migration value match", "At least 99.95 percent at mock 3", "Per mock"],
       ["Training completion", "At least 95 percent before go-live", "Fortnightly in G4"],
       ["Risk burn-down", "No open High risk without owner and date", "Weekly"]],
      [0.34, 0.40, 0.26]),
]


EXTRA["BrightPath Tech"]["11"] += [
    H("Appendix L: Next steps"),
    "If the Board is interested in our proposal, we would be delighted to arrange a friendly introductory call and "
    "a short online demonstration of QuickBill. We could then hold a brief workshop to talk about the Board's "
    "priorities and to sketch the first screens together. After that, we can prepare a refined plan and a final "
    "price for discussion. We look forward to hearing from the Board and to the possibility of working together.",
    T([["Step", "Suggested timing"],
       ["Introductory call", "Within a few days of the Board's response"],
       ["Demonstration of QuickBill", "Following week"],
       ["Requirements workshop", "Within two weeks"],
       ["Refined plan and price", "Shortly after the workshop"],
       ["Contract signature and kick-off", "As soon as the Board is ready"]],
      [0.5, 0.5]),
    H("Appendix M: Contact"),
    "Arjun Rao, Founder and Project Lead, BrightPath Tech LLP, Hyderabad. Email and phone details are available "
    "on request. We aim to respond to enquiries on the same day.",
]
EXTRA["NexaWorks"]["11"] += [
    H("Appendix E: Contact and next steps"),
    "NexaWorks is available to present this proposal and to demonstrate NexaBill to the evaluation committee. "
    "We suggest a two-hour session covering the tariff configuration workbench, the agent desktop, the integration "
    "monitoring console and a walkthrough of the gate plan and risk register. The proposed programme manager, "
    "solution architect and account manager will attend. Following selection, mobilisation can begin within 14 "
    "days of contract signature, with the project charter and governance plan delivered by the end of week 2.",
    T([["Step", "NexaWorks proposal", "Timing"],
       ["Clarification questions", "Written responses within 3 working days", "During evaluation"],
       ["Demonstration", "Two-hour session at Meridian HQ or online", "On request"],
       ["Reference calls", "Lakeview, Coastal Gas and Hillstate contacts available", "On request"],
       ["Contract and mobilisation", "Programme manager and architects start within 14 days", "After award"]],
      [0.26, 0.50, 0.24]),
]
EXTRA["Orbit Digital"]["11"] += [
    H("Appendix I: Next steps"),
    "Orbit would welcome the opportunity to present UtilityOne to the Board's evaluation committee and to discuss the "
    "discovery phase in more detail. We propose that, if selected, the first step would be a short mobilisation meeting "
    "to agree the discovery plan, followed by workshops with the Board's business and technology teams. At the end of "
    "discovery, Orbit will present a detailed plan, a refined estimate and a proposed team. The Board would then "
    "be able to confirm the next phases with a better understanding of the scope.",
    T([["Step", "Description"],
       ["Presentation", "UtilityOne demonstration and discussion at the Board's convenience"],
       ["Mobilisation", "Agree discovery plan and appoint counterparts"],
       ["Discovery", "Eight weeks of workshops and analysis"],
       ["Refined estimate", "Updated plan, team and price after discovery"],
       ["Configuration onwards", "Subject to Board approval of the refined plan"]],
      [0.30, 0.70]),
    "We thank the Board for the opportunity to respond and look forward to a long and productive partnership.",
]


EXTRA["BrightPath Tech"]["11"] += [
    H("Appendix N: Closing thoughts"),
    "We know that choosing a partner for a project of this importance is not easy. We hope that this proposal has "
    "given the Board a sense of who we are: an energetic, friendly and ambitious team with a genuine wish to help. "
    "We are not the biggest company, and we do not claim to know everything, but we are quick learners and we "
    "care deeply about our clients' success. Thank you for taking the time to consider BrightPath Tech.",
]
EXTRA["NexaWorks"]["11"] += [
    H("Appendix F: Document control"),
    T([["Item", "Detail"],
       ["Proposal reference", "NW-MRWB-2026-014-v1.0"],
       ["Prepared by", "NexaWorks bid team led by the proposed programme manager"],
       ["Approved by", "Chief delivery officer and chief financial officer"],
       ["Validity", "120 days from 2026-10-20"],
       ["Compliance", "No deviations from the mandatory requirements of the RFP are taken"],
       ["Confidentiality", "Commercial and security sections are confidential to the Board's evaluation committee"]],
      [0.28, 0.72]),
    "Any clarification issued by the Board before award will be incorporated through a written addendum to this "
    "proposal, with any price effect stated explicitly and approved by both parties before it takes effect.",
]
EXTRA["Orbit Digital"]["11"] += [
    H("Appendix J: Document information"),
    T([["Item", "Detail"],
       ["Prepared by", "Orbit Digital utilities bid team"],
       ["Version", "1.0"],
       ["Validity", "90 days from submission"],
       ["Pricing status", "Estimate; subject to confirmation after discovery"],
       ["Contact", "Engagement partner via the Orbit Digital Bengaluru office"]],
      [0.30, 0.70]),
    "Orbit regards this proposal as the starting point for a conversation. We expect that the details of scope, "
    "approach, team and price will be refined in discovery, and we look forward to working with the Board to do so.",
]


EXTRA["Orbit Digital"]["10"] += [
    "Other assumptions: the Board will make decisions promptly, will nominate counterparts for each workstream and will "
    "provide access to documentation about existing systems. Orbit has assumed that the scope is broadly similar to "
    "that of its previous water utility engagements; differences will be identified in discovery. Orbit will also rely on the Board to supply representative test data and to arrange user availability for workshops and acceptance testing.",
]
EXTRA["NexaWorks"]["11"] += [
    "NexaWorks also confirms that the key staff named in this proposal are committed for the duration of their "
    "gates, and that any replacement will be of equal or greater experience and subject to the Board's approval.",
]


def build_blank(path: str) -> None:
    """An image-only/blank PDF used to demonstrate the validation path (no extractable text)."""
    c = canvas.Canvas(path, pagesize=A4)
    c.setFillColor(colors.HexColor("#DDDDDD"))
    c.rect(60, 400, 470, 300, fill=1, stroke=0)  # looks like a scanned image block; no text layer
    c.showPage()
    c.save()


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for s in SUPPLIERS:
        print("wrote", build(s))
    blank = os.path.join(OUT_DIR, "Zenith_Scanned_Blank_Proposal.pdf")
    build_blank(blank)
    print("wrote", blank, "(validation demo: no extractable text)")
