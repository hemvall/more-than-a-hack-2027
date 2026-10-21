const assert = require('node:assert/strict');

function checkPolicy(pr, commits) {
  const branch = /^(feat|fix|docs|chore|ci|test|refactor|perf|build|experiment)\/([1-9]\d*)-[a-z0-9]+(?:-[a-z0-9]+)*$/.exec(pr.head.ref);
  assert(branch, 'Branch must be type/123-short-description');
  assert.equal(pr.base.ref, 'main', 'PR must target main');
  const issue = Number(branch[2]);
  const subject = /^(feat|fix|docs|chore|ci|test|refactor|perf|build|revert)\(#([1-9]\d*)\)!?: \S[^\r\n]*$/;
  function checkSubject(value, label) {
    const match = subject.exec(value);
    assert(match, label + ' must use type(#123): description');
    assert.equal(Number(match[2]), issue, label + ' must reference the branch issue');
  }
  checkSubject(pr.title, 'PR title');
  // Only accept a standalone closing line outside fenced code and HTML comments.
  const body = (pr.body || '').replace(/<!--[\s\S]*?-->/g, '')
    .replace(/^```[^\n]*\n[\s\S]*?^```[^\n]*$/gm, '')
    .replace(/^~~~[^\n]*\n[\s\S]*?^~~~[^\n]*$/gm, '');
  assert(new RegExp('^Closes #' + issue + '\\s*$', 'mi').test(body),
    'PR body needs a standalone Closes #' + issue + ' line');
  assert(commits.length > 0, 'PR must contain commits');
  for (const item of commits) {
    assert(item.parents.length < 2, 'Rebase instead of adding merge commits');
    checkSubject(item.commit.message.split('\n')[0], 'Commit ' + item.sha);
  }
  return issue;
}

module.exports = { checkPolicy };
