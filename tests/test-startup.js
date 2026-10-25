const assert = require('assert'), fs = require('fs'), path = require('path'), vm = require('vm');
const main = fs.readFileSync(path.join(__dirname, '../launcher/main.js'), 'utf8');
const watcher = main.slice(main.indexOf('  // ---------- return to the launcher ----------'), main.indexOf('  // Hooks for tv-test.js'));
function fixture(options = {}) {
  let now = 20000, foreground = 'self.Launcher', tick, worker, intervals = [], launches = [];
  const cfg = { returnToLauncher: true, launcherOnPowerOn: true, ...options };
  const tizen = { application: { launch: id => launches.push(id), getCurrentApplication: () => ({ hide() {} }) } };
  const appcommon = { getForegroundAppId: () => foreground };
  const context = { cfg, tizen, hasTizen: true, selfId: 'self.Launcher', lastKey: 0,
    Date: { now: () => now }, document: { hidden: false }, window: { webapis: { appcommon } }, webapis: { appcommon },
    clearInterval() {}, setInterval(fn) { intervals.push(fn); return intervals.length; },
    Worker: function () { worker = this; this.terminate = () => {}; }
  };
  vm.createContext(context); vm.runInContext(watcher + '\nwatchForeground();', context);
  tick = () => worker ? worker.onmessage() : intervals[0]();
  return { context, launches, tick, advance(ms) { now += ms; }, foreground(id) { foreground = id; context.document.hidden = id !== 'self.Launcher'; }, worker: () => worker, intervals };
}
let f = fixture(); f.tick(); f.foreground(null); f.advance(500); f.tick(); f.advance(10000); f.foreground('org.tizen.tv-viewer'); f.tick();
assert.deepEqual(f.launches, ['self.Launcher'], 'Observed standby returns from the input screen');
f = fixture(); f.tick(); f.advance(30000); f.foreground('org.tizen.tv-viewer'); f.tick();
assert.deepEqual(f.launches, ['self.Launcher'], 'Frozen timers recover when standby provided no foreground queries');
f = fixture(); f.tick(); f.advance(30000); f.foreground('netflix'); f.tick();
assert.equal(f.launches.length, 0, 'Resume never takes over a streaming app');
f = fixture(); vm.runInContext('pauseReturnUntil = Date.now() + 120000', f.context); f.advance(30000); f.foreground('com.samsung.tv.csfs'); f.tick();
assert.equal(f.launches.length, 0, 'Samsung Home escape remains available after a timer gap');
f = fixture({ launcherOnPowerOn: false }); f.advance(30000); f.foreground('org.tizen.tv-viewer'); f.tick();
assert.equal(f.launches.length, 0, 'Disabled wake feature does not reopen over an input');
f = fixture(); f.worker().onerror(); f.worker().onerror();
assert.equal(f.intervals.length, 1, 'A failed worker falls back once');
f.advance(30000); f.foreground('org.tizen.tv-viewer'); f.intervals[0](); assert.equal(f.launches.length, 1);
console.log('PASS: standby, suspended timers, streaming-app protection, Home escape, disabled wake, worker-error fallback.');
