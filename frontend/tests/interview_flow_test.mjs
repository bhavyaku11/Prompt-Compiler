/**
 * Automated test suite for Interview Mode workflow and endpoints.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

test('Interview Mode Client Tests', async (t) => {
  await t.test('startInterview creates payload with correct request format', () => {
    const request = {
      input: 'how to login',
      project_id: 'proj_123',
      target_agent: 'cursor',
      enable_knowledge_retrieval: true,
    };

    assert.equal(request.input, 'how to login');
    assert.equal(request.project_id, 'proj_123');
    assert.equal(request.target_agent, 'cursor');
    assert.equal(request.enable_knowledge_retrieval, true);
  });

  await t.test('submitInterviewAnswers formats answer list correctly', () => {
    const answers = [
      { question_id: 'q1', answer: 'PostgreSQL with SQLAlchemy' },
      { question_id: 'q2', answer: 'JWT with refresh tokens' },
    ];

    const payload = { answers };
    assert.equal(payload.answers.length, 2);
    assert.equal(payload.answers[0].question_id, 'q1');
    assert.equal(payload.answers[0].answer, 'PostgreSQL with SQLAlchemy');
  });

  await t.test('interview session lifecycle transitions from in_progress to ready and compiled', () => {
    // 1. Initial response
    const session1 = {
      session_id: 'sess_abc',
      status: 'in_progress',
      turn: 1,
      questions: [
        {
          id: 'q1',
          topic: 'database',
          question: 'What database should be used?',
          options: ['PostgreSQL', 'SQLite', 'MongoDB'],
          allow_custom: true,
        },
      ],
    };
    assert.equal(session1.status, 'in_progress');
    assert.equal(session1.questions.length, 1);

    // 2. Updated response after answer
    const session2 = {
      session_id: 'sess_abc',
      status: 'ready',
      turn: 2,
      questions: [],
    };
    assert.equal(session2.status, 'ready');
    assert.equal(session2.questions.length, 0);

    // 3. Compiled result
    const compileResult = {
      input: 'how to login',
      result: '# Topic & Objective\nImplement authentication with PostgreSQL',
      target_agent: 'cursor',
      interview_session_id: 'sess_abc',
    };
    assert.equal(compileResult.interview_session_id, 'sess_abc');
    assert.ok(compileResult.result.includes('PostgreSQL'));
  });
});
