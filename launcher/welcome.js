(function () {
  'use strict';
  var key = 'openhome.welcome.shown.v1', panel = null;
  function close() { if (panel && panel.parentNode) panel.parentNode.removeChild(panel); panel = null; }
  document.addEventListener('keydown', function (e) {
    if (!panel) return;
    if ([13, 10009, 27, 37, 38, 39, 40].indexOf(e.keyCode) >= 0) {
      e.preventDefault(); e.stopImmediatePropagation();
      if ([13, 10009, 27].indexOf(e.keyCode) >= 0) close();
    }
  }, true);
  setTimeout(function () {
    // Installation/restart checks use a pending configuration. Only the final
    // installer update enables the welcome; an early launch must not consume it.
    if (typeof LAUNCHER_LOCAL === 'undefined' || LAUNCHER_LOCAL.welcomeReady !== true) return;
    try { if (localStorage.getItem(key)) return; localStorage.setItem(key, '1'); }
    catch (e) { return; } // no reliable once-only storage: do not show a repeating welcome.
    panel = document.createElement('section');
    panel.id = 'openhome-welcome';
    panel.style.cssText = 'position:absolute;inset:0;z-index:500;box-sizing:border-box;background:linear-gradient(135deg,#103b39,#1c2350);color:#fff;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:70px';
    var profile = document.createElement('img'); profile.src = 'profile.jpg'; profile.alt = 'MalHani'; profile.width = 240; profile.height = 240; profile.style.cssText = 'width:240px;height:240px;flex-shrink:0;object-fit:cover;border-radius:50%;margin:0 0 28px';
    var title = document.createElement('h1'); title.textContent = 'Terima kasih guna installer ni.'; title.style.cssText = 'font-size:56px;max-width:1450px;margin:0 0 16px';
    var text = document.createElement('p'); text.textContent = 'Harap korang suka la launcher baru ni.\n\nAda banyak ruang lagi boleh custom. Enjoy!!!'; text.style.cssText = 'font-size:32px;line-height:1.5;max-width:1300px;white-space:pre-line;margin:0';
    var button = document.createElement('button'); button.textContent = "Let's go"; button.style.cssText = 'font-family:inherit;margin-top:32px;padding:20px 60px;background:#e4f4ed;color:#102b28;border:4px solid white;border-radius:25px;font-size:32px'; button.onclick = close;
    panel.appendChild(profile); panel.appendChild(title); panel.appendChild(text); panel.appendChild(button); document.getElementById('stage').appendChild(panel);
  }, 900);
})();
