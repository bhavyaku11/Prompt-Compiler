"""Controlled live test for Task 15: SQLite Persistence Foundation with Qwen3 4B."""

import asyncio
import os
import sys
import time

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ai.ollama import OllamaClient
from app.config import settings
from app.database.models import CompilationRecord, InterviewSessionRecord, RequirementAnalysisRecord
from app.database.repositories import (
    CompilationRepository,
    InterviewSessionRepository,
    RequirementAnalysisRepository,
)
from app.database.session import (
    get_engine,
    get_session_factory,
    init_db,
    reset_db_engine,
)
from app.engine.critic import PromptCritic
from app.engine.generator import PromptGenerator
from app.engine.interviewer import (
    InterviewAnswer,
    InterviewSessionStore,
    PromptInterviewer,
    SqliteInterviewSessionStore,
)
from app.engine.refiner import PromptRefiner
from app.engine.requirements import RequirementEngine
from app.templates.selector import TemplateSelector


async def main() -> None:
    print("==================================================")
    print("TASK 15: LIVE PERSISTENCE & RESTART VERIFICATION")
    print("Model: qwen3:4b (local Ollama)")
    print("==================================================")

    # 1. Setup live database path
    live_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "live_verification.db"))
    live_db_url = f"sqlite:///{live_db_path}"
    
    # Remove previous live test db if exists
    if os.path.exists(live_db_path):
        os.remove(live_db_path)

    print(f"\n[1] Initializing SQLite database at: {live_db_path}")
    reset_db_engine()
    engine = init_db(live_db_url)
    print("    -> Database initialized and tables verified.")

    # 2. Check Ollama availability
    import httpx
    ollama_client = OllamaClient(timeout=600.0)
    try:
        resp = httpx.get(f"{ollama_client.base_url}/api/tags", timeout=5.0)
        resp.raise_for_status()
        print(f"[2] Ollama connection verified: HTTP {resp.status_code} OK")
    except Exception as exc:
        print(f"[ERROR] Ollama is not reachable: {exc}")
        sys.exit(1)

    # 3. Setup engines
    req_engine = RequirementEngine(ollama_client=ollama_client)
    sqlite_store = SqliteInterviewSessionStore(database_url=live_db_url)
    req_repo = RequirementAnalysisRepository(database_url=live_db_url)
    interviewer = PromptInterviewer(
        ollama_client=ollama_client,
        session_store=sqlite_store,
        requirement_repository=req_repo,
    )

    # STEP 1 & 2: Start interview and receive question
    test_input = "Build a lightweight CLI tool in Python to monitor server memory usage and log alerts."
    print(f"\n[3] STEP 1: Starting interview with prompt:\n    '{test_input}'")
    session = await interviewer.start_session_async(
        input_text=test_input,
        requirement_engine=req_engine,
        use_llm=True,
    )
    print(f"    -> Session created: {session.session_id}")
    print(f"    -> Status: {session.status}, Turn: {session.turn}")
    print(f"    -> Unresolved topics: {session.unresolved_topics}")
    print(f"    -> Questions generated: {len(session.questions)}")
    for q in session.questions:
        print(f"       * [{q.id}] {q.topic}: {q.question}")

    # STEP 3: Submit answer
    if session.questions:
        target_q = session.questions[0]
        selected_answer = target_q.options[0] if target_q.options else "Log to a local JSON file"
        print(f"\n[4] STEP 2 & 3: Submitting answer for [{target_q.id}] '{target_q.topic}':\n    -> Answer: '{selected_answer}'")
        session = await interviewer.submit_answers_async(
            session_id=session.session_id,
            answers=[
                InterviewAnswer(
                    question_id=target_q.id,
                    answer=selected_answer,
                )
            ],
            use_llm=True,
        )
        print(f"    -> Updated status: {session.status}, Turn: {session.turn}")
        print(f"    -> Recorded answers: {session.answers}")

    # STEP 4: Verify session is persisted in SQLite
    print(f"\n[5] STEP 4: Verifying session directly in SQLite...")
    repo = InterviewSessionRepository(database_url=live_db_url)
    persisted_session = repo.get(session.session_id)
    assert persisted_session is not None, "Session must exist in SQLite database"
    assert persisted_session.session_id == session.session_id
    assert persisted_session.original_input == test_input
    print(f"    -> VERIFIED: Session {persisted_session.session_id} found in SQLite table 'interview_sessions'.")
    print(f"    -> Persisted answers: {persisted_session.answers}")

    # Also verify requirement analysis record
    persisted_analysis = req_repo.get_by_session_id(session.session_id)
    assert persisted_analysis is not None, "RequirementAnalysis must be persisted in SQLite"
    print(f"    -> VERIFIED: RequirementAnalysis found for session: {persisted_analysis.intent}")

    saved_session_id = session.session_id

    # STEP 5: SIMULATE BACKEND STOP / RESTART
    print(f"\n[6] STEP 5: Simulating backend server process restart...")
    # Destroy all in-memory references and close SQLite engine/pools
    reset_db_engine()
    del session
    del persisted_session
    del interviewer
    del sqlite_store
    del repo
    del req_repo
    time.sleep(0.5)
    print("    -> Process restart simulation complete (all in-memory state purged, engine reset).")

    # STEP 6: Retrieve session from fresh repository instance
    print(f"\n[7] STEP 6: Retrieving session after restart from fresh repository instance...")
    fresh_engine = init_db(live_db_url)
    fresh_repo = InterviewSessionRepository(database_url=live_db_url)
    restored_session = fresh_repo.get(saved_session_id)
    assert restored_session is not None, "Restored session must exist after restart"
    print(f"    -> VERIFIED: Session successfully restored from SQLite!")
    print(f"    -> Session ID: {restored_session.session_id}")
    print(f"    -> Original input: {restored_session.original_input}")
    print(f"    -> Confirmed requirements: {restored_session.current_analysis.confirmed_requirements}")

    # STEP 7: Compile using clarified requirements
    print(f"\n[8] STEP 7: Compiling final prompt using clarified requirements...")
    template_selector = TemplateSelector()
    prompt_generator = PromptGenerator(ollama_client=ollama_client, template_selector=template_selector)
    prompt_critic = PromptCritic(ollama_client=ollama_client)
    prompt_refiner = PromptRefiner(prompt_generator=prompt_generator, prompt_critic=prompt_critic)
    compilation_repo = CompilationRepository(database_url=live_db_url)

    # If status is not ready, force ready for compilation
    restored_session.status = "ready"
    fresh_repo.save(restored_session)

    initial_gen = await prompt_generator.generate_async(restored_session.current_analysis)
    refinement_result = await prompt_refiner.run_loop_async(
        analysis=restored_session.current_analysis,
        initial_generation=initial_gen,
        use_llm_critic=False,
    )
    print(f"    -> Compiled prompt generated (length: {len(refinement_result.final_prompt)} chars).")

    # Persist compilation record
    comp_rec = compilation_repo.save(
        input_text=restored_session.original_input,
        compiled_prompt=refinement_result.final_prompt,
        task_type=refinement_result.task_type,
        template_name=refinement_result.template_name,
        requirements_summary=restored_session.current_analysis.model_dump(),
        validation_summary=refinement_result.validation_result.model_dump(),
        refinement_attempts=refinement_result.refinement_attempts,
        interview_session_id=restored_session.session_id,
    )
    print(f"    -> Compilation record persisted with id: {comp_rec.id} (compilation_id: {comp_rec.compilation_id})")

    # STEP 8: Verify compilation record exists in SQLite
    print(f"\n[9] STEP 8: Verifying compilation record in SQLite...")
    fetched_comp = compilation_repo.get_by_id(comp_rec.compilation_id)
    assert fetched_comp is not None, "Compilation record must exist in SQLite database"
    assert fetched_comp.interview_session_id == restored_session.session_id
    assert fetched_comp.input_text == test_input
    print(f"    -> VERIFIED: Compilation record {fetched_comp.compilation_id} retrieved from SQLite!")
    print(f"    -> Associated interview session ID: {fetched_comp.interview_session_id}")
    print(f"    -> Refinement attempts: {fetched_comp.refinement_attempts}")

    print("\n==================================================")
    print("ALL 8 VERIFICATION STEPS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    asyncio.run(main())
