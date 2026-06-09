from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.branch import Branch
from app.models.knowledge_item import KnowledgeItem
from app.models.organization import Organization


@dataclass(frozen=True)
class FAQSeed:
    key: str
    question: str
    answer: str
    language: str = "en-US"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TenantSeed:
    slug: str
    name: str
    default_language: str
    supported_languages: tuple[str, ...]
    branch_slug: str
    branch_name: str
    handoff_number_masked: str
    faqs: tuple[FAQSeed, ...]


@dataclass
class SeedSummary:
    organizations_created: int = 0
    branches_created: int = 0
    knowledge_items_created: int = 0
    organizations_updated: int = 0
    branches_updated: int = 0
    knowledge_items_updated: int = 0


UNIVERSITY_FAQS: Final = (
    FAQSeed(
        "cse-cost",
        "CSE cost koto?",
        "CSE fees depend on the current semester, credit load, and approved waiver. "
        "Please request the latest official fee schedule or a callback before deciding.",
        "bn-Latn",
        ("cse", "fees"),
    ),
    FAQSeed(
        "admission-fee",
        "What is the admission fee?",
        "Admission fees can change by intake and program. Please confirm the current "
        "official amount with the admissions office.",
        tags=("admission", "fees"),
    ),
    FAQSeed(
        "admission-documents",
        "Which documents are needed for admission?",
        "Typical documents include academic certificates, transcripts, identification, "
        "and recent photographs. The admissions office will confirm the final checklist.",
        tags=("admission", "documents"),
    ),
    FAQSeed(
        "scholarship",
        "Are scholarships available?",
        "Scholarships may be available under current university policy. Eligibility and "
        "availability must be confirmed for the relevant intake.",
        tags=("scholarship",),
    ),
    FAQSeed(
        "waiver",
        "How does the tuition waiver work?",
        "Waiver rules depend on academic results and current policy. Please ask for an "
        "official eligibility review.",
        tags=("waiver", "fees"),
    ),
    FAQSeed(
        "office-hours",
        "Office time kokhon?",
        "The demo office schedule is Saturday to Thursday, 9 AM to 5 PM. Confirm before "
        "visiting because holiday schedules may differ.",
        "bn-Latn",
        ("office", "hours"),
    ),
    FAQSeed(
        "location",
        "Where is the Sylhet campus?",
        "This demo tenant represents a Sylhet campus. Use the verified map or address "
        "published by the organization before travelling.",
        tags=("location",),
    ),
    FAQSeed(
        "contact",
        "How can I contact admissions?",
        "Leave your name and a masked callback number, or request a human handoff to the "
        "admissions team.",
        tags=("contact",),
    ),
    FAQSeed(
        "callback",
        "Can someone call me back?",
        "Yes. The agent can record a callback request with your preferred time and area "
        "of interest.",
        tags=("callback",),
    ),
    FAQSeed(
        "program-list",
        "Which programs are offered?",
        "The demo program list includes CSE, Business, and English. Confirm the active "
        "program list with admissions.",
        tags=("programs",),
    ),
    FAQSeed(
        "application-deadline",
        "What is the application deadline?",
        "The deadline is a demo placeholder and is not verified. Please request the "
        "current intake deadline from admissions.",
        tags=("application", "deadline"),
    ),
    FAQSeed(
        "payment-method",
        "How can I pay the admission fee?",
        "Use only payment methods listed on the organization's verified official "
        "channels. Never send money to a number supplied only during an unverified call.",
        tags=("payment", "safety"),
    ),
    FAQSeed(
        "online-application",
        "Can I apply online?",
        "Online application may be available. Use only the verified application link "
        "provided by the university.",
        tags=("application", "online"),
    ),
    FAQSeed(
        "admission-test",
        "Is there an admission test?",
        "Admission test requirements vary by program and intake. Confirm the current "
        "requirement with admissions.",
        tags=("admission", "test"),
    ),
    FAQSeed(
        "class-schedule",
        "When are classes held?",
        "Class schedules vary by department and semester. The department office can "
        "provide the current routine.",
        tags=("classes", "schedule"),
    ),
    FAQSeed(
        "credit-transfer",
        "Is credit transfer accepted?",
        "Credit transfer is subject to academic review and current policy. Submit "
        "official transcripts for evaluation.",
        tags=("credit-transfer",),
    ),
    FAQSeed(
        "hostel",
        "Is hostel accommodation available?",
        "Accommodation availability is not verified in this demo knowledge set. Please "
        "request a callback for the latest information.",
        tags=("hostel",),
    ),
    FAQSeed(
        "transport",
        "Does the university provide transport?",
        "Transport routes and availability can change. Ask the campus office for the "
        "current verified route list.",
        tags=("transport",),
    ),
    FAQSeed(
        "international-students",
        "Can international students apply?",
        "International applications may require additional documents and immigration "
        "checks. Contact admissions for the official process.",
        tags=("international", "admission"),
    ),
    FAQSeed(
        "human-handoff",
        "I need to speak with a person.",
        "I can request a human handoff. If nobody is available, I can record a callback "
        "request without guessing an answer.",
        tags=("handoff",),
    ),
)

SCHOOL_FAQS: Final = (
    FAQSeed(
        "admission-fee",
        "What is the school admission fee?",
        "Admission fees depend on class level and the current session. Please request the "
        "latest official fee sheet from the school office.",
        tags=("admission", "fees"),
    ),
    FAQSeed(
        "admission-documents",
        "Which documents are needed for school admission?",
        "Typical documents include the student's birth registration, photographs, prior "
        "school records, and guardian identification. Confirm the final checklist.",
        tags=("admission", "documents"),
    ),
    FAQSeed(
        "scholarship",
        "Does the school offer scholarships?",
        "Scholarship support may be available under current school policy. The office "
        "must confirm eligibility and available places.",
        tags=("scholarship",),
    ),
    FAQSeed(
        "waiver",
        "Is any fee waiver available?",
        "Fee waivers depend on approved policy and individual review. Please request an "
        "official assessment from the school.",
        tags=("waiver", "fees"),
    ),
    FAQSeed(
        "office-hours",
        "School office time kokhon?",
        "The demo office schedule is Sunday to Thursday, 8 AM to 3 PM. Confirm before "
        "visiting because holidays may change the schedule.",
        "bn-Latn",
        ("office", "hours"),
    ),
    FAQSeed(
        "location",
        "Where is the Sylhet school branch?",
        "This demo tenant represents a Sylhet branch. Check the organization's verified "
        "address or map before travelling.",
        tags=("location",),
    ),
    FAQSeed(
        "contact",
        "How can I contact the school office?",
        "You can request a human handoff or leave a callback request with your name and "
        "the student's class of interest.",
        tags=("contact",),
    ),
    FAQSeed(
        "callback",
        "Can the school call me back?",
        "Yes. The agent can record a callback request and your preferred contact time.",
        tags=("callback",),
    ),
    FAQSeed(
        "program-list",
        "Which classes or programs are available?",
        "The demo school covers primary and secondary levels. Confirm current class "
        "availability and sections with the office.",
        tags=("classes", "programs"),
    ),
    FAQSeed(
        "application-deadline",
        "When is the school application deadline?",
        "The deadline is a demo placeholder and is not verified. Please ask the school "
        "office for the current session deadline.",
        tags=("application", "deadline"),
    ),
    FAQSeed(
        "payment-method",
        "How can school fees be paid?",
        "Pay only through methods published by the school's verified official channels. "
        "Do not send money to an unverified personal number.",
        tags=("payment", "safety"),
    ),
    FAQSeed(
        "admission-test",
        "Is there an admission test?",
        "Assessment requirements vary by class. The school office can confirm the current "
        "process and syllabus.",
        tags=("admission", "test"),
    ),
    FAQSeed(
        "age-requirement",
        "What is the age requirement?",
        "Age requirements depend on class and current education policy. Submit the birth "
        "registration for an official eligibility check.",
        tags=("age", "admission"),
    ),
    FAQSeed(
        "school-hours",
        "What are the school hours?",
        "School hours vary by shift and class. The office can provide the current routine.",
        tags=("school", "hours"),
    ),
    FAQSeed(
        "transport",
        "Is school transport available?",
        "Transport routes and seats can change. Ask the school office for the current "
        "verified route list.",
        tags=("transport",),
    ),
    FAQSeed(
        "uniform",
        "Where can I get the school uniform?",
        "Use the uniform specification or supplier information published by the school. "
        "Confirm details before purchasing.",
        tags=("uniform",),
    ),
    FAQSeed(
        "books",
        "Which books are required?",
        "The book list depends on class and session. Request the current approved list "
        "from the school office.",
        tags=("books",),
    ),
    FAQSeed(
        "guardian-meeting",
        "When are guardian meetings held?",
        "Meeting dates vary by term. The school will provide the verified schedule through "
        "its official communication channels.",
        tags=("guardian", "meeting"),
    ),
    FAQSeed(
        "results",
        "How can guardians check results?",
        "Use the school's verified result channel or contact the office. The agent should "
        "not disclose private student results.",
        tags=("results", "privacy"),
    ),
    FAQSeed(
        "human-handoff",
        "I need to speak with the school office.",
        "I can request a human handoff. If the office is unavailable, I can record a "
        "callback request.",
        tags=("handoff",),
    ),
)

SERVICE_FAQS: Final = (
    FAQSeed(
        "service-cost",
        "How much does the service cost?",
        "Service pricing depends on scope and requirements. Request a written quotation "
        "before approving any work.",
        tags=("service", "pricing"),
    ),
    FAQSeed(
        "booking-fee",
        "Is there a booking or admission fee?",
        "Any booking fee must appear in an official written quotation. Confirm the amount "
        "before payment.",
        tags=("booking", "fees"),
    ),
    FAQSeed(
        "required-documents",
        "Which documents are needed to start?",
        "Required documents depend on the service. Share only the minimum information "
        "listed in the verified service checklist.",
        tags=("documents", "privacy"),
    ),
    FAQSeed(
        "discount",
        "Are discounts or waivers available?",
        "Discounts may be offered under current campaigns. Ask for a written, verified "
        "quotation showing any approved discount.",
        tags=("discount", "waiver"),
    ),
    FAQSeed(
        "office-hours",
        "Office time kokhon?",
        "The demo office schedule is Saturday to Thursday, 9 AM to 6 PM. Confirm before "
        "visiting because holiday schedules may differ.",
        "bn-Latn",
        ("office", "hours"),
    ),
    FAQSeed(
        "location",
        "Where is the service office?",
        "This demo company has a Sylhet service branch. Use the verified company address "
        "or map before visiting.",
        tags=("location",),
    ),
    FAQSeed(
        "contact",
        "How can I contact support?",
        "Request a human handoff or leave a callback request with a short description of "
        "the service you need.",
        tags=("contact", "support"),
    ),
    FAQSeed(
        "callback",
        "Can someone call me back?",
        "Yes. The agent can record a callback request and preferred time.",
        tags=("callback",),
    ),
    FAQSeed(
        "service-list",
        "Which services are available?",
        "The demo list includes consultation, installation, maintenance, and support. "
        "Confirm the current service catalogue before booking.",
        tags=("services",),
    ),
    FAQSeed(
        "application-deadline",
        "Is there a deadline to request service?",
        "Any deadline shown here is a demo placeholder. Confirm scheduling and campaign "
        "deadlines with the service team.",
        tags=("deadline", "booking"),
    ),
    FAQSeed(
        "payment-method",
        "How can I pay?",
        "Pay only through methods printed on a verified invoice or official company "
        "channel. Never transfer funds to an unverified personal number.",
        tags=("payment", "safety"),
    ),
    FAQSeed(
        "quotation",
        "Can I get a quotation?",
        "Yes. Provide the service type and basic requirements, and the team can prepare a "
        "written quotation.",
        tags=("quotation",),
    ),
    FAQSeed(
        "appointment",
        "How do I book an appointment?",
        "Leave your preferred date and contact time. The team must confirm the booking.",
        tags=("appointment",),
    ),
    FAQSeed(
        "coverage-area",
        "Which areas do you serve?",
        "Coverage depends on service type and team availability. Ask for confirmation for "
        "your location.",
        tags=("coverage", "location"),
    ),
    FAQSeed(
        "response-time",
        "How quickly will the team respond?",
        "Response time varies with workload and urgency. A callback request does not "
        "guarantee an exact response time.",
        tags=("support", "response-time"),
    ),
    FAQSeed(
        "warranty",
        "Is there a warranty?",
        "Warranty terms depend on the specific service and written agreement. Review the "
        "official terms before purchase.",
        tags=("warranty",),
    ),
    FAQSeed(
        "cancellation",
        "Can I cancel a booking?",
        "Cancellation rules depend on the written booking terms. Contact the team before "
        "the scheduled work.",
        tags=("cancellation",),
    ),
    FAQSeed(
        "complaint",
        "How do I submit a complaint?",
        "Provide the service reference and a short description. The agent can record the "
        "issue or request a human handoff.",
        tags=("complaint", "support"),
    ),
    FAQSeed(
        "data-privacy",
        "What personal information should I share?",
        "Share only information necessary for the service. Do not provide passwords, API "
        "keys, payment PINs, or one-time codes.",
        tags=("privacy", "security"),
    ),
    FAQSeed(
        "human-handoff",
        "I need to speak with a representative.",
        "I can request a human handoff. If nobody is available, I can record a callback "
        "request without inventing an answer.",
        tags=("handoff",),
    ),
)

DEMO_TENANTS: Final = (
    TenantSeed(
        slug="demo-university-sylhet",
        name="Demo University Sylhet",
        default_language="bn-BD",
        supported_languages=("bn-BD", "bn-Latn", "syl-BD", "en-US"),
        branch_slug="sylhet-campus",
        branch_name="Sylhet Campus",
        handoff_number_masked="*******0001",
        faqs=UNIVERSITY_FAQS,
    ),
    TenantSeed(
        slug="demo-school-sylhet",
        name="Demo School Sylhet",
        default_language="bn-BD",
        supported_languages=("bn-BD", "bn-Latn", "syl-BD", "en-US"),
        branch_slug="sylhet-school",
        branch_name="Sylhet School Branch",
        handoff_number_masked="*******0002",
        faqs=SCHOOL_FAQS,
    ),
    TenantSeed(
        slug="demo-service-company",
        name="Demo Service Company",
        default_language="en-US",
        supported_languages=("en-US", "bn-BD", "bn-Latn", "syl-BD"),
        branch_slug="sylhet-service",
        branch_name="Sylhet Service Branch",
        handoff_number_masked="*******0003",
        faqs=SERVICE_FAQS,
    ),
)


def seed_demo_tenants(session: Session) -> SeedSummary:
    summary = SeedSummary()
    for tenant_seed in DEMO_TENANTS:
        organization = session.scalar(
            select(Organization).where(Organization.slug == tenant_seed.slug)
        )
        if organization is None:
            organization = Organization(slug=tenant_seed.slug, name=tenant_seed.name)
            session.add(organization)
            session.flush()
            summary.organizations_created += 1
        else:
            summary.organizations_updated += 1

        organization.name = tenant_seed.name
        organization.default_language = tenant_seed.default_language
        organization.supported_languages = list(tenant_seed.supported_languages)
        organization.timezone = "Asia/Dhaka"
        organization.handoff_settings = {
            "enabled": True,
            "mode": "mock",
            "fallback_number_masked": tenant_seed.handoff_number_masked,
        }

        branch = session.scalar(
            select(Branch).where(
                Branch.organization_id == organization.id,
                Branch.slug == tenant_seed.branch_slug,
            )
        )
        if branch is None:
            branch = Branch(
                organization_id=organization.id,
                slug=tenant_seed.branch_slug,
                name=tenant_seed.branch_name,
            )
            session.add(branch)
            session.flush()
            summary.branches_created += 1
        else:
            summary.branches_updated += 1

        branch.name = tenant_seed.branch_name
        branch.city = "Sylhet"
        branch.region = "Sylhet"
        branch.country = "BD"
        branch.address = "Demo address; replace with a verified organization address."
        branch.phone = None
        branch.timezone = "Asia/Dhaka"

        for faq_seed in tenant_seed.faqs:
            source_reference = f"{tenant_seed.slug}:{faq_seed.key}"
            knowledge_item = session.scalar(
                select(KnowledgeItem).where(
                    KnowledgeItem.organization_id == organization.id,
                    KnowledgeItem.source_type == "demo_seed",
                    KnowledgeItem.source_reference == source_reference,
                )
            )
            if knowledge_item is None:
                knowledge_item = KnowledgeItem(
                    organization_id=organization.id,
                    source_type="demo_seed",
                    source_reference=source_reference,
                )
                session.add(knowledge_item)
                summary.knowledge_items_created += 1
            else:
                summary.knowledge_items_updated += 1

            knowledge_item.branch_id = branch.id
            knowledge_item.question = faq_seed.question
            knowledge_item.answer = faq_seed.answer
            knowledge_item.language = faq_seed.language
            knowledge_item.tags = list(faq_seed.tags)
            knowledge_item.status = "approved"

    session.flush()
    return summary


def main() -> None:
    with SessionLocal.begin() as session:
        summary = seed_demo_tenants(session)

    print(
        "Demo seed complete: "
        f"organizations +{summary.organizations_created}/~{summary.organizations_updated}, "
        f"branches +{summary.branches_created}/~{summary.branches_updated}, "
        "knowledge items "
        f"+{summary.knowledge_items_created}/~{summary.knowledge_items_updated}"
    )


if __name__ == "__main__":
    main()
