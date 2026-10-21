const { test } = require('node:test');
const assert = require('node:assert/strict');
const { checkPolicy } = require('./check-policy.cjs');
const pr = () => ({ head: { ref: 'chore/12-workflow' }, base: { ref: 'main' },
  title: 'chore(#12): set up checks', body: 'Closes #12' });
const commits = () => [{ sha: 'abc', parents: [{}],
  commit: { message: 'ci(#12): add checks\n\nDetails' } }];

test('accepts matching issue references and mixed commit types', () => {
  assert.equal(checkPolicy(pr(), commits()), 12);
});
test('accepts breaking changes and experiment branches', () => {
  const p = pr(); p.head.ref = 'experiment/12-temporal-model'; p.title = 'feat(#12)!: change output';
  assert.equal(checkPolicy(p, commits()), 12);
});
for (const [name, edit] of [
  ['missing branch issue', p => { p.head.ref = 'feat/model'; }],
  ['wrong base', p => { p.base.ref = 'develop'; }],
  ['wrong title issue', p => { p.title = 'feat(#13): other'; }],
  ['missing closing line', p => { p.body = ''; }],
  ['wrong closing issue', p => { p.body = 'Closes #123'; }],
  ['commented closing line', p => { p.body = '<!--\nCloses #12\n-->'; }],
  ['code-only closing line', p => { p.body = '```\nCloses #12\n```'; }],
  ['title with newline', p => { p.title += '\nextra'; }],
]) {
  test('rejects ' + name, () => {
    const p = pr(); edit(p); assert.throws(() => checkPolicy(p, commits()));
  });
}
test('rejects unrelated commits, merge commits and empty lists', () => {
  const c = commits(); c[0].commit.message = 'fix(#13): other';
  assert.throws(() => checkPolicy(pr(), c));
  c[0].commit.message = 'fix(#12): other'; c[0].parents.push({});
  assert.throws(() => checkPolicy(pr(), c));
  assert.throws(() => checkPolicy(pr(), []));
});
