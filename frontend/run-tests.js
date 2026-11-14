const { execSync } = require('child_process');
const fs = require('fs');
const junitPath = process.argv[2];
let atoms = [];
// Read atoms from stdin if available
if (!process.stdin.isTTY) {
  let input = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => input += chunk);
  process.stdin.on('end', () => {
    atoms = input.trim().split(/\s+/).filter(Boolean);
    runTests(junitPath, atoms);
  });
} else {
  atoms = process.argv.slice(3);
  runTests(junitPath, atoms);
}
function runTests(junitPath, atoms) {
  const cmd = `npx vitest run --reporter=junit --outputFile="${junitPath}" ${atoms.map(a => `"${a}"`).join(' ')}`;
  console.log('Running:', cmd);
  try {
    execSync(cmd, { stdio: 'inherit', shell: true });
  } catch (e) {
    process.exit(e.status || 1);
  }
}
