(function () {
  'use strict';
  window.mountLauncherTools = function (api) {
    var cfg = api.cfg, prefs = {}, mode = 'dock', cursor = 0, tab = 0, items = [], page = '', offset = 0;
    try { prefs = JSON.parse(localStorage.getItem('launcher-preferences') || '{}'); } catch (e) {}
    var defaults = (cfg.favorites || []).slice();
    if (typeof prefs.clock24h === 'boolean') cfg.clock24h = prefs.clock24h;
    if ([10, 30, 60, 300].indexOf(prefs.rotation) >= 0) cfg.wallpapers.minutes = prefs.rotation / 60;
    if (Array.isArray(prefs.favorites) && prefs.favorites.length && prefs.favorites.length <= 6) cfg.favorites = prefs.favorites;
    function persist() { try { localStorage.setItem('launcher-preferences', JSON.stringify(prefs)); } catch (e) { api.toast('Could not save preferences'); } }
    function visibility() {
      document.getElementById('clock').style.display = prefs.clockHidden ? 'none' : '';
      document.getElementById('solat').style.display = (prefs.prayerHidden || (cfg.prayer && cfg.prayer.enabled === false)) ? 'none' : '';
    }
    visibility();
    var bar = document.createElement('nav'); bar.id = 'tools-bar'; bar.setAttribute('aria-label', 'Launcher tools');
    var labels = ['TV Settings', 'Apps', 'Inputs', 'Customize'];
    labels.forEach(function (label, i) {
      var b = document.createElement('button'); b.textContent = label;
      b.onclick = function () { tab = i; activateTab(); }; bar.appendChild(b);
    });
    var hint = document.createElement('p'); hint.id = 'tools-hint'; hint.textContent = '↑ Tools     Enter Open     Back twice Samsung Home';
    var panel = document.createElement('section'); panel.id = 'tools-panel'; panel.hidden = true;
    document.getElementById('stage').appendChild(bar); document.getElementById('stage').appendChild(hint); document.getElementById('stage').appendChild(panel);
    function mark() {
      Array.prototype.forEach.call(bar.children, function (b, i) { b.classList.toggle('selected', mode === 'bar' && i === tab); });
      var buttons = panel.querySelectorAll('button');
      Array.prototype.forEach.call(buttons, function (b, i) { b.classList.toggle('selected', i === cursor); });
    }
    function dock() { mode = 'dock'; panel.hidden = true; api.focus(); mark(); }
    function toolbar() { mode = 'bar'; panel.hidden = true; api.blur(); mark(); }
    function show(title, entries, id) {
      page = id; items = entries; cursor = 0; mode = 'panel'; api.blur(); panel.hidden = false; panel.textContent = '';
      var h = document.createElement('h1'); h.textContent = title; panel.appendChild(h);
      var grid = document.createElement('div'); grid.className = 'tools-grid'; panel.appendChild(grid);
      entries.forEach(function (entry, i) {
        var b = document.createElement('button'); var name = document.createElement('strong'); name.textContent = entry.title; b.appendChild(name);
        if (entry.detail) { var small = document.createElement('small'); small.textContent = entry.detail; b.appendChild(small); }
        b.onclick = function () { cursor = i; choose(); }; grid.appendChild(b);
      });
      var foot = document.createElement('p'); foot.textContent = 'Arrow keys to move · Enter to select · Back to close'; panel.appendChild(foot); mark();
    }
    function native(title, id, detail) {
      return { title: title, detail: detail, run: function () { dock(); api.launch({ id: id, name: title }); } };
    }
    function settings() {
      show('TV Settings & Tools', [
        native('All Settings', 'org.tizen.menu', 'Picture · Sound · Network · Accessibility'),
        native('Samsung Apps', 'com.samsung.tv.store', 'Find and install TV apps'),
        native('SmartThings', 'com.samsung.tv.SmartThingsApp', 'Connected devices'),
        native('User Guide', '26emanual3.emanual', 'TV help and instructions'),
        { title: 'Samsung Home', detail: 'Open the original Home screen', run: function () { dock(); api.home(); } },
        { title: 'Back to Launcher', run: dock }
      ], 'settings');
    }
    // Only user-facing apps: Samsung's inventory also includes internal services and factory tools.
    var builtins = ['org.tizen.netflix-app', 'org.tizen.primevideo', 'org.tizen.browser', 'com.samsung.tv.SmartThingsApp', 'com.samsung.tv.SecurityCenter'];
    function userApps() {
      return api.apps().filter(function (a) {
        return builtins.indexOf(a.id) >= 0 || (/^[a-zA-Z0-9]{10}\./.test(a.id) && !/service|emanual|boot|factory|test|launcher|epop|promotion/i.test(a.id + ' ' + a.name));
      });
    }
    function apps(edit, start) {
      offset = start || 0;
      var list = userApps(), entries = list.slice(offset, offset + 6).map(function (a) {
        var selected = cfg.favorites.some(function (f) { return (f.match || []).indexOf(a.id) >= 0; });
        return { title: (edit && selected ? '✓ ' : '') + a.name, detail: edit ? (selected ? 'Remove from favourites' : 'Add to favourites') : 'Open app', run: function () {
          if (!edit) { dock(); api.launch(a); return; }
          if (selected && cfg.favorites.length === 1) { api.toast('Keep at least one favourite'); return; }
          if (!selected && cfg.favorites.length >= 6) { api.toast('Up to 6 favourites. Remove one first.'); return; }
          cfg.favorites = cfg.favorites.filter(function (f) { return (f.match || []).indexOf(a.id) < 0; });
          if (!selected) cfg.favorites.push({ title: a.name, match: [a.id], image: 'icon', fit: 'mark' });
          prefs.favorites = cfg.favorites; persist(); api.changed(); api.blur(); apps(true, offset);
        } };
      });
      if (offset) entries.push({ title: 'Previous page', run: function () { apps(edit, offset - 6); } });
      if (offset + 6 < list.length) entries.push({ title: 'Next page', run: function () { apps(edit, offset + 6); } });
      if (!edit) entries.push(native('Samsung Apps', 'com.samsung.tv.store', 'Install more apps'));
      entries.push({ title: edit ? 'Done' : 'Back', run: edit ? customize : toolbar });
      show(edit ? 'Choose Favourites (' + cfg.favorites.length + '/6)' : 'Installed Apps', entries, edit ? 'favorites' : 'apps');
    }
    function inputs() {
      var sources = ['TV1', 'HDMI1', 'HDMI2', 'HDMI3'];
      function render(connected) {
        show('TV & HDMI Inputs', sources.map(function (s) { return { title: s === 'TV1' ? 'Live TV' : s.replace('HDMI', 'HDMI '), detail: connected ? (connected.indexOf(s) >= 0 ? 'Connected' : 'No device signal') : 'Switch input', run: function () { dock(); api.source(s); } }; }), 'inputs');
      }
      render(null);
      try { tizen.systeminfo.getPropertyValue('VIDEOSOURCE', function (info) {
        if (page === 'inputs' && mode === 'panel') render(info.connected.map(function (s) { return s.type + s.number; }));
      }, function () {}); } catch (e) {}
    }
    function customize() {
      var seconds = prefs.rotation || 30;
      show('Customize Launcher', [
        { title: 'Clock: ' + (cfg.clock24h ? '24-hour' : '12-hour'), run: function () { cfg.clock24h = !cfg.clock24h; prefs.clock24h = cfg.clock24h; persist(); api.changed(); api.blur(); customize(); } },
        { title: 'Clock: ' + (prefs.clockHidden ? 'Hidden' : 'Shown'), run: function () { prefs.clockHidden = !prefs.clockHidden; persist(); visibility(); customize(); } },
        { title: 'Waktu Solat: ' + (prefs.prayerHidden ? 'Hidden' : 'Shown'), detail: ((cfg.prayer && cfg.prayer.place) || '') + ' · JAKIM ' + ((cfg.prayer && cfg.prayer.zone) || 'SGR01'), run: function () { prefs.prayerHidden = !prefs.prayerHidden; persist(); visibility(); customize(); } },
        { title: 'Background: ' + seconds + ' seconds', detail: 'Change picture rotation speed', run: function () { var speeds = [10, 30, 60, 300]; prefs.rotation = speeds[(speeds.indexOf(seconds) + 1) % speeds.length]; persist(); api.rotation(prefs.rotation); customize(); } },
        { title: 'Next Background', detail: 'Cycle through the current pictures', run: function () { api.wallpaper(); } },
        { title: 'Favourite Apps', detail: 'Choose up to 6 dock shortcuts', run: function () { apps(true, 0); } },
        { title: 'Restore Default Favourites', run: function () { cfg.favorites = defaults.slice(); prefs.favorites = cfg.favorites; persist(); api.changed(); api.blur(); customize(); } },
        { title: 'Back to Launcher', run: dock }
      ], 'customize');
    }
    function activateTab() { [settings, function () { apps(false, 0); }, inputs, customize][tab](); }
    function choose() { if (items[cursor]) items[cursor].run(); mark(); }
    document.addEventListener('keydown', function (e) {
      var k = e.keyCode;
      if (mode === 'dock' && k !== 38) return;
      if ([37, 38, 39, 40, 13, 10009, 27].indexOf(k) < 0) return;
      e.preventDefault(); e.stopImmediatePropagation();
      if (api.busy()) return;
      if (mode === 'dock') { toolbar(); return; }
      if (k === 10009 || k === 27) { if (mode === 'panel') toolbar(); else dock(); return; }
      if (mode === 'bar') {
        if (k === 37) tab = Math.max(0, tab - 1);
        if (k === 39) tab = Math.min(3, tab + 1);
        if (k === 40) dock();
        if (k === 13) activateTab();
      } else {
        if (k === 37 && cursor % 2) cursor--;
        if (k === 39 && cursor % 2 === 0 && cursor + 1 < items.length) cursor++;
        if (k === 38) cursor = Math.max(0, cursor - 2);
        if (k === 40) cursor = Math.min(items.length - 1, cursor + 2);
        if (k === 13) choose();
      }
      mark();
    }, true);
  };
})();
