"""Deterministic benchmark dataset for Prompt Compiler quality evaluation."""

from app.benchmark.schemas import BenchmarkCase


BENCHMARK_DATASET: list[BenchmarkCase] = [
    # -------------------------------------------------------------
    # 1. BUILD: Build feature from vague requirement with explicit constraints
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-BUILD-01",
        title="User Authentication Service with JWT",
        task_type="build",
        category="build",
        input_text=(
            "We need user authentication. Implement JWT authentication with registration, "
            "login, and SQLite session storage. Do not use external authentication services like "
            "Auth0 or Supabase. Keep the user model simple with email and password."
        ),
        description="Builds an authentication flow from a common feature request with negative constraints.",
        expected_requirements=[
            "JWT authentication",
            "registration",
            "login",
            "SQLite",
            "email",
            "password",
        ],
        expected_constraints=[
            "Do not use external authentication services like Auth0 or Supabase",
        ],
        expected_technologies=["JWT", "SQLite"],
        forbidden_assumptions=[
            "MongoDB",
            "PostgreSQL",
            "Auth0",
            "Supabase",
            "Docker",
            "Redis",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 2. MODIFY: Modify existing checkout flow with explicit backward-compatibility invariant
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-MODIFY-01",
        title="Stripe Webhook Signature Verification",
        task_type="modify",
        category="modify",
        input_text=(
            "Update our Stripe checkout endpoint to support webhook notifications. "
            "Add webhook signature verification and handle payment_intent.succeeded events. "
            "Do not change the existing checkout callback URL /api/checkout/callback and "
            "preserve backward compatibility with the existing order schema."
        ),
        description="Modifies an active payments integration while strictly enforcing invariant routes and schema.",
        expected_requirements=[
            "Stripe webhook notifications",
            "signature verification",
            "payment_intent.succeeded",
        ],
        expected_constraints=[
            "Do not change the existing checkout callback URL /api/checkout/callback",
            "preserve backward compatibility with the existing order schema",
        ],
        expected_technologies=["Stripe"],
        forbidden_assumptions=[
            "PayPal",
            "GraphQL",
            "Kubernetes",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 3. DEBUG: Diagnose and fix race condition in chunked file upload
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-DEBUG-01",
        title="File Upload Race Condition",
        task_type="debug",
        category="debug",
        input_text=(
            "Fix a race condition in our file upload handler where concurrent chunk writes cause "
            "corrupted output files. Add mutex or lock synchronization to ensure chunks are written "
            "in sequence. Do not alter the 1MB chunk size and do not introduce third-party cloud storage."
        ),
        description="Diagnoses concurrent chunk writes and prescribes synchronization without altering chunk specifications.",
        expected_requirements=[
            "race condition",
            "chunk write",
            "synchronization",
        ],
        expected_constraints=[
            "Do not alter the 1MB chunk size",
            "do not introduce third-party cloud storage",
        ],
        expected_technologies=[],
        forbidden_assumptions=[
            "AWS S3",
            "Google Cloud Storage",
            "Celery",
            "RabbitMQ",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 4. EXPLAIN: Explain rate limiting algorithm and behavior
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-EXPLAIN-01",
        title="Sliding Window Rate Limiter Explanation",
        task_type="explain",
        category="explain",
        input_text=(
            "Explain how our sliding window rate limiter middleware works, specifically "
            "how in-memory request timestamps are tracked and expired. Do not alter the middleware "
            "interface or suggest external storage systems."
        ),
        description="Requests a technical explanation of an internal rate limiter algorithm with strict scope limits.",
        expected_requirements=[
            "sliding window rate limiter",
            "in-memory request timestamps",
            "expired",
        ],
        expected_constraints=[
            "Do not alter the middleware interface",
            "do not suggest external storage systems",
        ],
        expected_technologies=[],
        forbidden_assumptions=[
            "Redis cluster",
            "Nginx sidecar",
            "Memcached",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 5. ANALYZE: Performance analysis of database migration queries
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-ANALYZE-01",
        title="Database Migration Query Bottleneck Analysis",
        task_type="analyze",
        category="analyze",
        input_text=(
            "Analyze the performance bottlenecks in our large-table database migration script. "
            "Evaluate index creation, query execution plans, and batch update sizes. "
            "Do not drop existing foreign key constraints and ensure the migration can run without downtime."
        ),
        description="Analyzes migration efficiency while enforcing foreign key and zero-downtime constraints.",
        expected_requirements=[
            "performance bottlenecks",
            "database migration",
            "index creation",
            "batch update sizes",
        ],
        expected_constraints=[
            "Do not drop existing foreign key constraints",
            "ensure the migration can run without downtime",
        ],
        expected_technologies=[],
        forbidden_assumptions=[
            "NoSQL migration",
            "Cassandra",
            "DynamoDB",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 6. PROJECT CONTEXT DEPENDENT: Task relying on persistent project context
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-CTX-01",
        title="Profile Photo Upload with Project Baseline Context",
        task_type="build",
        category="project_context",
        input_text=(
            "Add a profile photo upload feature for registered users. Support JPEG and PNG, "
            "and generate a 128x128 thumbnail on upload. Follow all existing project conventions."
        ),
        description="Evaluates whether prompt generation adheres to project memory constraints and technologies.",
        expected_requirements=[
            "profile photo upload",
            "JPEG and PNG",
            "128x128 thumbnail",
        ],
        expected_constraints=[
            "Local filesystem storage under uploads/",
            "Async FastAPI endpoints only",
        ],
        expected_technologies=["FastAPI", "Pillow"],
        forbidden_assumptions=[
            "AWS S3",
            "Cloudinary",
            "Flask",
            "Django",
        ],
        project_context={
            "description": "Local-first photo gallery app",
            "technologies": ["FastAPI", "Pillow", "SQLite"],
            "constraints": ["Local filesystem storage under uploads/", "No cloud storage dependencies"],
            "coding_rules": ["Async FastAPI endpoints only", "Pydantic models for all payloads"],
        },
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 7. SINGLE-SOURCE KNOWLEDGE: Task requiring local knowledge retrieval
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-KNOW-01",
        title="Schema-Aligned Authentication Implementation",
        task_type="modify",
        category="knowledge",
        input_text=(
            "Update the user login endpoint to verify credentials against the existing project "
            "UserTable schema. Use bcrypt for password hash verification."
        ),
        description="Evaluates single-document retrieval precision and fidelity to indexed documentation.",
        expected_requirements=[
            "user login endpoint",
            "UserTable schema",
            "bcrypt",
        ],
        expected_constraints=[
            "verify credentials against the existing project UserTable schema",
        ],
        expected_technologies=["bcrypt"],
        forbidden_assumptions=[
            "scrypt",
            "Argon2",
            "Firebase Auth",
        ],
        knowledge_sources=[
            {
                "source_name": "docs/database_schema.md",
                "source_type": "documentation",
                "content": (
                    "# Database Schema\n\n"
                    "## UserTable\n"
                    "Table `users` contains:\n"
                    "- `id`: UUID primary key\n"
                    "- `email`: unique string\n"
                    "- `password_hash`: bcrypt hashed string\n"
                    "- `created_at`: timestamp\n"
                    "All authentication must query `users` and verify `password_hash`."
                ),
            },
        ],
        expected_knowledge_sources=["docs/database_schema.md"],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 8. MULTI-SOURCE KNOWLEDGE: Multi-document retrieval synthesis
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-MULTI-01",
        title="Invoice Generation with Multi-Document Project Context",
        task_type="build",
        category="multi_source",
        input_text=(
            "Create an automated invoice PDF generator service. Use the existing database "
            "Invoice model schema, format the tax calculation per accounting specs, and "
            "render the output using our existing internal PDF utility."
        ),
        description="Verifies that multiple relevant files across docs and code are synthesized into contextual evidence.",
        expected_requirements=[
            "invoice PDF generator",
            "Invoice model",
            "tax calculation",
            "internal PDF utility",
        ],
        expected_constraints=[
            "use existing Invoice model schema",
            "render output using existing internal PDF utility",
        ],
        expected_technologies=["Python"],
        forbidden_assumptions=[
            "ReportLab",
            "Stripe Invoicing API",
            "WeasyPrint",
            "Node.js",
        ],
        knowledge_sources=[
            {
                "source_name": "docs/accounting_spec.md",
                "source_type": "documentation",
                "content": (
                    "# Accounting Specification\n\n"
                    "Invoices must calculate subtotal, standard VAT rate (20%), and grand total.\n"
                    "Invoices must include invoice number format: INV-{YEAR}-{ID}."
                ),
            },
            {
                "source_name": "src/models/invoice.py",
                "source_type": "code",
                "content": (
                    "class Invoice(Base):\n"
                    "    __tablename__ = 'invoices'\n"
                    "    id = Column(Integer, primary_key=True)\n"
                    "    invoice_number = Column(String, unique=True)\n"
                    "    amount_cents = Column(Integer, nullable=False)\n"
                    "    status = Column(String, default='draft')\n"
                ),
            },
            {
                "source_name": "src/utils/pdf_renderer.py",
                "source_type": "code",
                "content": (
                    "def render_invoice_pdf(data: dict) -> bytes:\n"
                    "    '''Internal utility rendering an invoice dict to PDF bytes.'''\n"
                    "    # Renders template using internal engine\n"
                    "    pass\n"
                ),
            },
        ],
        expected_knowledge_sources=[
            "docs/accounting_spec.md",
            "src/models/invoice.py",
            "src/utils/pdf_renderer.py",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 9. NEGATIVE CONSTRAINTS: Heavy negative constraints evaluation
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-NEG-01",
        title="Zero-Dependency Local Search Engine",
        task_type="build",
        category="negative_constraints",
        input_text=(
            "Implement a fast search feature for our documentation catalog using plain Python "
            "substring and token matching. Do not use Elasticsearch, do not use vector embeddings, "
            "do not use external search APIs, and do not use SQLite FTS."
        ),
        description="Stress tests negative constraint adherence and anti-hallucination guardrails.",
        expected_requirements=[
            "search feature",
            "plain Python",
            "token matching",
        ],
        expected_constraints=[
            "Do not use Elasticsearch",
            "do not use vector embeddings",
            "do not use external search APIs",
            "do not use SQLite FTS",
        ],
        expected_technologies=["Python"],
        forbidden_assumptions=[
            "Elasticsearch",
            "Pinecone",
            "Algolia",
            "OpenSearch",
            "sqlite-vec",
        ],
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),

    # -------------------------------------------------------------
    # 10. PRECEDENCE CONFLICT: User explicit requirement overrides memory baseline
    # -------------------------------------------------------------
    BenchmarkCase(
        benchmark_id="BM-CONFLICT-01",
        title="User Override of Project Baseline Database",
        task_type="modify",
        category="precedence",
        input_text=(
            "For this local development milestone, migrate our database connection from "
            "PostgreSQL to SQLite. Update the connection string and table initialization."
        ),
        description="Tests that current explicit user requirement overrides a conflicting project memory technology.",
        expected_requirements=[
            "migrate database connection",
            "SQLite",
            "connection string",
        ],
        expected_constraints=[
            "migrate our database connection from PostgreSQL to SQLite",
        ],
        expected_technologies=["SQLite"],
        forbidden_assumptions=[
            "remain on PostgreSQL",
            "MySQL",
            "MongoDB",
        ],
        project_context={
            "description": "Enterprise app with PostgreSQL backend",
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "constraints": ["Production uses PostgreSQL on AWS RDS"],
            "coding_rules": ["SQLAlchemy ORM"],
        },
        applicable_agent_targets=["generic", "cursor", "claude_code", "cline", "windsurf"],
    ),
]


def get_benchmark_case(case_id: str) -> BenchmarkCase | None:
    """Lookup a benchmark case by its ID."""
    for case in BENCHMARK_DATASET:
        if case.benchmark_id == case_id:
            return case
    return None


def get_benchmark_cases(category: str | None = None) -> list[BenchmarkCase]:
    """Retrieve all benchmark cases, optionally filtered by category."""
    if category is None:
        return list(BENCHMARK_DATASET)
    return [c for c in BENCHMARK_DATASET if c.category == category or c.task_type == category]
