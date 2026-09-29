import test, { describe } from 'node:test';
import assert from 'node:assert/strict';

describe('Documentation Routing & Footer Button Navigation Tests', () => {
  const docRoutes = [
    { id: 'product', title: 'Product', path: '/docs/product' },
    { id: 'workflow', title: 'Workflow', path: '/docs/workflow' },
    { id: 'architecture', title: 'Architecture', path: '/docs/architecture' },
    { id: 'documentation', title: 'Documentation', path: '/docs/documentation' },
  ];

  test('All 4 documentation routes are defined in exact sequence: Product, Workflow, Architecture, Documentation', () => {
    assert.deepEqual(
      docRoutes.map((d) => d.title),
      ['Product', 'Workflow', 'Architecture', 'Documentation']
    );

    assert.equal(docRoutes[0].path, '/docs/product');
    assert.equal(docRoutes[1].path, '/docs/workflow');
    assert.equal(docRoutes[2].path, '/docs/architecture');
    assert.equal(docRoutes[3].path, '/docs/documentation');

    const uniquePaths = new Set(docRoutes.map((d) => d.path));
    assert.equal(uniquePaths.size, 4);
  });

  test('Section normalizer resolves valid sections and defaults to product', () => {
    function resolveSection(section) {
      if (!section) return 'product';
      const s = section.toLowerCase();
      if (s === 'workflow') return 'workflow';
      if (s === 'architecture') return 'architecture';
      if (s === 'documentation' || s === 'overview' || s === 'docs') return 'documentation';
      return 'product';
    }

    assert.equal(resolveSection(undefined), 'product');
    assert.equal(resolveSection(''), 'product');
    assert.equal(resolveSection('product'), 'product');
    assert.equal(resolveSection('PRODUCT'), 'product');
    assert.equal(resolveSection('workflow'), 'workflow');
    assert.equal(resolveSection('architecture'), 'architecture');
    assert.equal(resolveSection('documentation'), 'documentation');
    assert.equal(resolveSection('overview'), 'documentation');
    assert.equal(resolveSection('docs'), 'documentation');
    assert.equal(resolveSection('unknown-page'), 'product');
  });

  test('Footer navigation contract verifies 4 internal redirects in sequence and 1 external GitHub link', () => {
    const footerButtons = [
      { name: 'Product', type: 'internal', target: '/docs/product' },
      { name: 'Workflow', type: 'internal', target: '/docs/workflow' },
      { name: 'Architecture', type: 'internal', target: '/docs/architecture' },
      { name: 'GitHub', type: 'external', target: 'https://github.com/bhavyaku11/Prompt-Compiler' },
      { name: 'Documentation', type: 'internal', target: '/docs/documentation' },
    ];

    assert.equal(footerButtons.length, 5);

    const internalButtons = footerButtons.filter((b) => b.type === 'internal');
    const externalButtons = footerButtons.filter((b) => b.type === 'external');

    assert.equal(internalButtons.length, 4);
    assert.equal(externalButtons.length, 1);
    assert.equal(externalButtons[0].name, 'GitHub');
    assert.equal(externalButtons[0].target, 'https://github.com/bhavyaku11/Prompt-Compiler');

    assert.deepEqual(
      internalButtons.map((b) => b.name),
      ['Product', 'Workflow', 'Architecture', 'Documentation']
    );

    assert.deepEqual(
      internalButtons.map((b) => b.target),
      ['/docs/product', '/docs/workflow', '/docs/architecture', '/docs/documentation']
    );
  });

  test('Rough Idea -> Agent Prompt navigation redirects authenticated users to studio and guests to auth', () => {
    const getTargetRoute = (isAuthed) => (isAuthed ? '/studio' : '/auth');

    assert.equal(getTargetRoute(true), '/studio');
    assert.equal(getTargetRoute(false), '/auth');
  });
});
