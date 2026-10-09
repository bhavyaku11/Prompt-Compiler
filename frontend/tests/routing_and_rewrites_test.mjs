import test, { describe } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, '..');
const repoRootDir = path.resolve(frontendDir, '..');

describe('SPA Routing and Vercel Rewrites Tests', () => {
  test('frontend/vercel.json exists and routes client-side routes to /index.html while excluding /api', () => {
    const vercelConfigPath = path.join(frontendDir, 'vercel.json');
    assert.ok(fs.existsSync(vercelConfigPath), 'frontend/vercel.json should exist');

    const config = JSON.parse(fs.readFileSync(vercelConfigPath, 'utf8'));
    assert.ok(Array.isArray(config.rewrites), 'rewrites should be an array');

    const spaRewrite = config.rewrites.find((r) => r.destination === '/index.html');
    assert.ok(spaRewrite, 'rewrites should contain rule routing to /index.html');

    // Convert source string to regex and test coverage
    const sourceRegex = new RegExp(`^${spaRewrite.source}$`);
    assert.ok(sourceRegex.test('/auth'), 'should rewrite /auth');
    assert.ok(sourceRegex.test('/studio'), 'should rewrite /studio');
    assert.ok(sourceRegex.test('/sign-in'), 'should rewrite /sign-in');
    assert.ok(sourceRegex.test('/sign-up'), 'should rewrite /sign-up');
    assert.ok(sourceRegex.test('/sso-callback'), 'should rewrite /sso-callback');
    assert.ok(sourceRegex.test('/docs'), 'should rewrite /docs');
    assert.ok(sourceRegex.test('/docs/architecture'), 'should rewrite /docs/architecture');

    // Ensure /api endpoints are NOT intercepted by rewrite
    assert.equal(sourceRegex.test('/api'), false, 'should NOT rewrite /api');
    assert.equal(sourceRegex.test('/api/'), false, 'should NOT rewrite /api/');
    assert.equal(sourceRegex.test('/api/health'), false, 'should NOT rewrite /api/health');
    assert.equal(sourceRegex.test('/api/compile'), false, 'should NOT rewrite /api/compile');
  });

  test('root vercel.json exists with build command, output directory, and rewrites', () => {
    const rootVercelConfigPath = path.join(repoRootDir, 'vercel.json');
    assert.ok(fs.existsSync(rootVercelConfigPath), 'root vercel.json should exist');

    const config = JSON.parse(fs.readFileSync(rootVercelConfigPath, 'utf8'));
    assert.ok(Array.isArray(config.rewrites), 'rewrites should be an array');
    assert.equal(config.outputDirectory, 'frontend/dist');

    const spaRewrite = config.rewrites.find((r) => r.destination === '/index.html');
    assert.ok(spaRewrite, 'root rewrites should contain rule routing to /index.html');

    const sourceRegex = new RegExp(`^${spaRewrite.source}$`);
    assert.ok(sourceRegex.test('/auth'), 'root rewrite should match /auth');
    assert.ok(sourceRegex.test('/studio'), 'root rewrite should match /studio');
    assert.equal(sourceRegex.test('/api/health'), false, 'root rewrite should NOT match /api/health');
  });

  test('Built frontend entry point exists at output location', () => {
    const indexPath = path.join(frontendDir, 'dist', 'index.html');
    assert.ok(fs.existsSync(indexPath), 'frontend/dist/index.html must exist as output entry point');
  });

  test('Root package.json contains build script for Vercel root deployments', () => {
    const rootPkgPath = path.join(repoRootDir, 'package.json');
    const pkg = JSON.parse(fs.readFileSync(rootPkgPath, 'utf8'));

    assert.ok(pkg.scripts, 'scripts object should exist in root package.json');
    assert.ok(pkg.scripts.build, 'build script should exist in root package.json');
    assert.match(pkg.scripts.build, /frontend/);
  });
});
