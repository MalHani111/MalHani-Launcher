'use strict';
// TV-side boot service bundled with MalHani Launcher.
var target = 'OpenHomeTV.Launcher';
var timer = null, keepalive = null, started = false, finished = false, attempts = 0;
function retry(error) {
  if (finished || !started) return;
  console.log('MalHani startup: launch attempt failed: ' + (error && error.name || 'unknown'));
  if (attempts >= 15 || (error && /SecurityError|NotFoundError/.test(error.name))) {
    finished = true;
    return;
  }
  timer = setTimeout(attempt, 2000);
}
function attempt() {
  if (!started || finished) return;
  timer = null;
  attempts++;
  try {
    tizen.application.launch(target, function () {
      finished = true;
      console.log('MalHani startup: launcher start accepted.');
    }, retry);
  } catch (error) { retry(error); }
}
module.exports = {
  onStart: function () {
    if (started) return;
    started = true;
    finished = false;
    attempts = 0;
    // Keep the service idle after success; do not repeatedly steal foreground.
    keepalive = setInterval(function () {}, 60000);
    attempt();
  },
  onRequest: function () {},
  onStop: function () {
    started = false;
    clearTimeout(timer);
    clearInterval(keepalive);
    timer = null; keepalive = null;
  }
};
