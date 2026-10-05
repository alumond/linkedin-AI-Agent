// Run with: node --test tests/test_review_ui.cjs
// Exercise the page's asynchronous approval flow without saving real approvals.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const html = readFileSync(require('node:path').join(__dirname, '../web/review.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const receipt = {approved_at: '2026-09-26T11:48:24+00:00', draft_sha256: 'draft', asset_sha256: 'image', publication_status: 'queued'};
const snapshot = (approved = false) => ({
  token: 'test', draft_sha256: 'draft', asset_sha256: 'image',
  pending: {draft: {alt_text: 'Test image'}, citations: []}, commentary: 'A test post.',
  approved, approval: approved ? receipt : null, image_ready: true,
  checks: [{ok: true, label: 'Checks passed'}], history: [], history_count: 0,
  require_approval: true, schedule: 'Publishes after approval · Morning checks at 07:17 and 11:17 Lagos', image_url: '/api/image',
});
const reply = (data, ok = true) => ({ok, json: async () => data});
const tick = () => new Promise(resolve => setImmediate(resolve));

async function page() {
  const element = () => ({
    textContent: '', value: '', hidden: false, disabled: false, className: '', open: false,
    setAttribute() {}, replaceChildren() {}, append() {}, addEventListener() {}, focus() {},
    close() { this.open = false; }, showModal() { this.open = true; },
  });
  const elements = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], element()]));
  const requests = [];
  let fetcher = async () => reply(snapshot());
  const context = vm.createContext({
    document: {getElementById: id => elements[id], createElement: element},
    fetch: (...args) => { requests.push(args); return fetcher(...args); },
  });
  vm.runInContext(script, context);
  await tick();
  return {context, elements, requests, fetch: f => { fetcher = f; }};
}

test('preparation shows progress and prevents repeat submissions until a refresh', async () => {
  const p = await page();
  const empty = {...snapshot(), pending: null, image_ready: false, preparing: false};
  p.fetch(async () => reply(empty));
  await p.context.load();
  let finish;
  p.fetch(() => new Promise(resolve => { finish = resolve; }));
  const preparing = p.context.prepare();
  assert.equal(p.elements.prepare.disabled, true);
  assert.equal(p.elements.prepare.textContent, 'Starting preparation…');
  await p.context.prepare();
  assert.equal(p.requests.filter(([path]) => path === '/api/prepare').length, 1);
  finish(reply({preparing: true, message: 'Draft preparation started.'}));
  await preparing;
  assert.equal(p.elements.prepare.disabled, true);
  assert.equal(p.elements.status.textContent, 'Preparing your post');
  assert.equal(p.elements.emptyTitle.textContent, 'Your next post is being prepared.');
  assert.equal(p.elements.notice.className, 'notice');
  await p.context.prepare();
  assert.equal(p.requests.filter(([path]) => path === '/api/prepare').length, 1);
  p.fetch(async () => reply({...empty, preparing: true}));
  await p.context.load();
  assert.equal(p.elements.prepare.disabled, true);
  p.fetch(async () => reply(snapshot()));
  await p.context.load();
  assert.equal(p.elements.status.textContent, 'Awaiting review');
  assert.equal(p.elements.empty.hidden, true);
});

test('a failed preparation request does not claim it started', async () => {
  const p = await page();
  p.fetch(async () => reply({error: 'GitHub is unavailable.'}, false));
  await p.context.prepare();
  assert.equal(p.elements.prepare.disabled, false);
  assert.equal(p.elements.notice.className, 'notice error');
  assert.equal(p.elements.notice.textContent, 'GitHub is unavailable.');
});

test('approval shows progress, prevents duplicate clicks, and keeps its receipt after refresh', async () => {
  const p = await page();
  assert.equal(p.elements.approve.disabled, false);
  assert.equal(p.elements.approvalStatus.hidden, true);
  let finish;
  p.fetch(() => new Promise(resolve => { finish = resolve; }));
  const saving = p.context.approve();
  assert.equal(p.elements.approve.textContent, 'Saving approval…');
  assert.equal(p.elements.approvalStatus.hidden, false);
  assert.equal(p.elements.refresh.disabled, true);
  assert.equal(p.elements.changes.disabled, true);
  await p.context.approve();
  assert.equal(p.requests.filter(([path]) => path === '/api/approve').length, 1);
  finish(reply({approval: receipt}));
  await saving;
  assert.equal(p.elements.approvalTitle.textContent, '✓ Publication queued');
  assert.match(p.elements.approvalTime.textContent, /12:48 Lagos/);
  assert.match(p.elements.approvalDetail.textContent, /queued for publication/);
  assert.equal(p.elements.approve.disabled, true);
  assert.equal(p.elements.changes.disabled, false);
  p.fetch(async () => reply(snapshot(true)));
  await p.context.load();
  assert.equal(p.elements.approvalTitle.textContent, '✓ Publication queued');
  assert.equal(p.elements.approvalStatus.hidden, false);
  assert.equal(p.elements.status.textContent, 'Publication queued');
  p.fetch(async () => reply(snapshot(false)));
  await p.context.load();
  assert.equal(p.elements.approvalStatus.hidden, true);
  assert.equal(p.elements.approve.disabled, false);
});

test('lost response asks for a refresh and recovers a remotely saved approval', async () => {
  const p = await page();
  p.fetch(async () => { throw Error('Connection interrupted.'); });
  await p.context.approve();
  assert.equal(p.elements.approvalTitle.textContent, 'Approval not confirmed');
  assert.match(p.elements.approvalDetail.textContent, /Refresh to check/);
  assert.equal(p.elements.approve.disabled, true);
  assert.equal(p.elements.refresh.disabled, false);
  await p.context.load(); // A failed refresh must not allow a duplicate submission.
  assert.equal(p.elements.approve.disabled, true);
  p.fetch(async () => reply(snapshot(true)));
  await p.context.load();
  assert.equal(p.elements.approvalTitle.textContent, '✓ Publication queued');
  assert.equal(p.elements.approvalStatus.hidden, false);
});

test('rejected approval never shows success and refresh enables a safe retry', async () => {
  const p = await page();
  p.fetch(async () => reply({error: 'The preview changed.'}, false));
  await p.context.approve();
  assert.equal(p.elements.approvalTitle.textContent, 'Approval not confirmed');
  assert.match(p.elements.approvalDetail.textContent, /The preview changed/);
  p.fetch(async () => reply(snapshot()));
  await p.context.load();
  assert.equal(p.elements.approvalStatus.hidden, true);
  assert.equal(p.elements.approve.disabled, false);
});

test('saving changes shows progress, prevents duplicate requests, and immediately confirms the save', async () => {
  const p = await page();
  p.elements.note.value = 'Focus on the data analysis.';
  p.context.openFeedback();
  let finish;
  p.fetch(() => new Promise(resolve => { finish = resolve; }));
  const saving = p.context.changes();
  assert.equal(p.elements.saveChanges.textContent, 'Saving request…');
  assert.equal(p.elements.saveChanges.disabled, true);
  assert.equal(p.elements.cancelChanges.disabled, true);
  assert.equal(p.elements.note.disabled, true);
  assert.equal(p.elements.feedbackStatus.hidden, false);
  assert.equal(p.elements.approve.disabled, true);
  await p.context.changes();
  assert.equal(p.requests.filter(([path]) => path === '/api/changes').length, 1);
  const feedback = {draft_sha256: 'draft', note: p.elements.note.value, status: 'revision_requested'};
  finish(reply({feedback, revision_started: true, message: 'Change request saved.'}));
  await saving;
  assert.equal(p.elements.feedback.open, false);
  assert.equal(p.elements.notice.textContent, 'Change request saved.');
  assert.equal(p.elements.approve.disabled, true);
  assert.equal(p.elements.changes.disabled, false);
  assert.equal(p.requests.length, 2); // No slow second snapshot before confirming success.
  p.fetch(async () => reply({...snapshot(), feedback}));
  await p.context.load();
  assert.match(p.elements.revisionStatus.textContent, /Change request saved/);
});

test('blank and rejected requests keep the text and show the error inside the dialog', async () => {
  const p = await page();
  p.context.openFeedback();
  p.elements.note.value = '  ';
  await p.context.changes();
  assert.equal(p.requests.length, 1);
  assert.match(p.elements.feedbackStatus.textContent, /Enter a specific/);
  p.elements.note.value = 'Focus on analysis';
  p.fetch(async () => reply({error: 'The publisher is preparing a post.'}, false));
  await p.context.changes();
  assert.equal(p.elements.feedback.open, true);
  assert.equal(p.elements.note.value, 'Focus on analysis');
  assert.equal(p.elements.feedbackStatus.hidden, false);
  assert.match(p.elements.feedbackStatus.textContent, /publisher is preparing/);
  assert.equal(p.elements.refreshFeedback.hidden, false);
  assert.equal(p.elements.saveChanges.disabled, false);
});

test('lost save response keeps the text and requires checking saved status before retrying', async () => {
  const p = await page();
  p.elements.note.value = 'Focus on analysis';
  p.context.openFeedback();
  p.fetch(async () => { throw Error('Connection interrupted.'); });
  await p.context.changes();
  assert.equal(p.elements.feedback.open, true);
  assert.equal(p.elements.saveChanges.disabled, true);
  assert.equal(p.elements.refreshFeedback.hidden, false);
  await p.context.load();
  assert.equal(p.elements.saveChanges.disabled, true);
  p.fetch(async () => reply({...snapshot(), feedback: {draft_sha256: 'draft', note: 'Focus on analysis'}}));
  await p.context.load();
  assert.match(p.elements.feedbackStatus.textContent, /request was saved/);
  assert.equal(p.elements.approve.disabled, true);
});

test('saved requests remain confirmed when dispatch fails, and revision failures are visible on refresh', async () => {
  const p = await page();
  p.elements.note.value = 'Focus on analysis';
  const feedback = {draft_sha256: 'draft', note: p.elements.note.value};
  p.fetch(async () => reply({feedback, revision_started: false, message: 'Saved, but revision could not start.'}));
  await p.context.changes();
  assert.match(p.elements.notice.textContent, /Saved, but/);
  assert.equal(p.elements.notice.className, 'notice error');
  assert.equal(p.elements.approve.disabled, true);
  p.fetch(async () => reply({...snapshot(), feedback: {...feedback, status: 'revision_failed', error: 'Post too long.'}}));
  await p.context.load();
  assert.equal(p.elements.status.textContent, 'Revision needs attention');
  assert.match(p.elements.revisionStatus.textContent, /Post too long/);
  assert.match(p.elements.revisionStatus.className, /error/);
  assert.equal(p.elements.approve.disabled, false);
  assert.equal(p.elements.approve.textContent, 'Approve current version');
  assert.match(p.elements.revisionStatus.textContent, /approve the current version/);
  p.fetch(async () => reply({...snapshot(), draft_sha256: 'revised', feedback}));
  await p.context.load();
  assert.equal(p.elements.revisionStatus.hidden, true);
  assert.equal(p.elements.approve.disabled, false);
});

test('real project screenshots are labelled as screenshots', async () => {
  const p = await page();
  p.fetch(async () => reply({...snapshot(), review: {provider: 'project_screenshot', alt_text: 'Original project screenshot'}}));
  await p.context.load();
  assert.equal(p.elements.imageStatus.textContent, 'Project screenshot · reviewed');
  assert.equal(p.elements.image.alt, 'Original project screenshot');
  assert.equal(p.elements.image.hidden, false);
});

test('performance results save and refresh the ten-post scorecard', async () => {
  const p = await page();
  const post = {post_urn: 'urn:li:share:test', topic: 'Measured post'};
  p.context.openMetrics(post);
  p.elements.metricImpressions.value = '140';
  p.elements.metricReactions.value = '2';
  p.elements.metricComments.value = '1';
  const scorecard = {measured_posts: 1, window_posts: 10, median_impressions: 140,
    baseline_impressions: 80, target_median_impressions: 120,
    posts_with_reactions: 1, target_posts_with_reactions: 5,
    posts_with_comments: 1, target_posts_with_comments: 3};
  p.fetch(async path => path === '/api/metrics'
    ? reply({message: 'Performance metrics saved.', scorecard})
    : reply({...snapshot(), scorecard}));
  await p.context.saveMetrics();
  assert.equal(p.requests.filter(([path]) => path === '/api/metrics').length, 1);
  assert.equal(p.elements.metrics.open, false);
  assert.equal(p.elements.medianImpressions.textContent, '140');
  assert.equal(p.elements.notice.textContent, 'Performance metrics saved.');
});


test('a failed dispatch exposes a retry without claiming the post is queued', async () => {
  const p = await page();
  p.fetch(async () => reply({...snapshot(true), approval: {...receipt, publication_status: 'dispatch_failed'}}));
  await p.context.load();
  assert.equal(p.elements.approve.textContent, 'Retry publication');
  assert.equal(p.elements.approve.disabled, false);
  assert.match(p.elements.approvalDetail.textContent, /could not start/);
  p.fetch(async () => reply({approval: receipt}));
  await p.context.approve();
  assert.equal(p.elements.approve.textContent, 'Publication queued ✓');
  assert.equal(p.elements.approve.disabled, true);
});
